"""Versioned, explainable research checks over stored report evidence."""

from datetime import timedelta
from decimal import Decimal
from typing import TYPE_CHECKING

from risk.models import RiskFinding, RiskPolicy

if TYPE_CHECKING:
    from reports.models import ResearchReport


def pointer_key(value: str) -> str:
    return value.replace("~", "~0").replace("/", "~1")


def identify(report: "ResearchReport", policy: RiskPolicy) -> list[RiskFinding]:
    findings = []

    def add(code, category, severity, message, ref, observed=None, threshold=None):
        findings.append(
            RiskFinding(
                code=code,
                category=category,
                severity=severity,
                message=message,
                evidence_refs=[ref],
                observed=observed,
                threshold=threshold,
            )
        )

    for index, warning in enumerate(report.risks):
        add("evidence_warning", "data_quality", "medium", warning, f"/risks/{index}")
    for index, missing in enumerate(report.missing_data):
        add(
            "missing_input",
            "data_quality",
            "info",
            f"Missing: {missing}.",
            f"/missing_data/{index}",
        )
    technical = report.technicals
    if technical:
        for metric, threshold, code, message, above in (
            (
                "volatility_20_annualized",
                policy.annualized_volatility,
                "high_volatility",
                "Annualized trailing volatility exceeds the research threshold.",
                True,
            ),
            (
                "max_drawdown",
                policy.drawdown,
                "historical_drawdown",
                "Observed peak-to-trough drawdown reaches the research threshold.",
                False,
            ),
        ):
            value = getattr(technical, metric)
            if value is not None and (value > threshold if above else value <= threshold):
                add(code, "technical", "medium", message, f"/technicals/{metric}", value, threshold)
        if technical.rsi14 is not None and (technical.rsi14 >= 70 or technical.rsi14 <= 30):
            add(
                "rsi_extreme",
                "technical",
                "info",
                "RSI is outside the 30–70 range; this does not predict a reversal.",
                "/technicals/rsi14",
                technical.rsi14,
                Decimal(70) if technical.rsi14 >= 70 else Decimal(30),
            )
    fundamental = report.fundamentals
    if fundamental:
        for metric, threshold, code, message, above in (
            (
                "revenue_growth",
                Decimal(0),
                "revenue_contraction",
                "Year-over-year revenue declined.",
                False,
            ),
            (
                "net_margin",
                Decimal(0),
                "net_loss",
                "The supplied financial period reports a net loss.",
                False,
            ),
            (
                "free_cash_flow",
                Decimal(0),
                "negative_fcf",
                "Free cash flow is negative for the supplied period.",
                False,
            ),
            (
                "current_ratio",
                policy.current_ratio,
                "low_current_ratio",
                "Current assets are below current liabilities.",
                False,
            ),
            (
                "debt_to_equity",
                policy.debt_to_equity,
                "high_debt_to_equity",
                "Debt/equity exceeds the research threshold.",
                True,
            ),
        ):
            value = getattr(fundamental, metric)
            if value is not None and (value > threshold if above else value < threshold):
                add(
                    code,
                    "fundamental",
                    "medium",
                    message,
                    f"/fundamentals/{metric}",
                    value,
                    threshold,
                )
        equity = fundamental.evidence.current.equity
        if (
            fundamental.evidence.retrieved_at <= report.generated_at
            and equity is not None
            and equity <= 0
        ):
            add(
                "nonpositive_book_equity",
                "fundamental",
                "high",
                "Reported book equity is nonpositive; debt/equity is not meaningful.",
                "/fundamentals/evidence/current/equity",
                equity,
                Decimal(0),
            )
    portfolio = report.portfolio
    if portfolio and portfolio.state == "available":
        if portfolio.equity <= 0:
            add(
                "nonpositive_portfolio_equity",
                "portfolio",
                "high",
                "Supplied portfolio equity is nonpositive.",
                "/portfolio/equity",
                portfolio.equity,
                Decimal(0),
            )
        if (
            portfolio.gross_leverage is not None
            and portfolio.gross_leverage > policy.gross_leverage
        ):
            add(
                "gross_leverage",
                "portfolio",
                "high",
                "Gross equity exposure exceeds portfolio equity.",
                "/portfolio/gross_leverage",
                portfolio.gross_leverage,
                policy.gross_leverage,
            )
        if portfolio.short_value > 0:
            add(
                "short_exposure",
                "portfolio",
                "medium",
                "The snapshot includes short equity exposure.",
                "/portfolio/short_value",
                portfolio.short_value,
            )
        if portfolio.cash_value < 0:
            add(
                "negative_cash",
                "portfolio",
                "medium",
                "Net cash is negative in the supplied snapshot.",
                "/portfolio/cash_value",
                portfolio.cash_value,
            )
        for groups, threshold, code in (
            ("by_symbol", policy.symbol_concentration, "symbol_concentration"),
            ("by_sector", policy.sector_concentration, "sector_concentration"),
        ):
            for name, exposure in sorted(getattr(portfolio, groups).items()):
                if exposure.gross_weight is not None and exposure.gross_weight > threshold:
                    add(
                        code,
                        "portfolio",
                        "medium",
                        f"{name} gross exposure exceeds the research concentration threshold.",
                        f"/portfolio/{groups}/{pointer_key(name)}/gross_weight",
                        exposure.gross_weight,
                        threshold,
                    )
    if report.news:
        for index, event in enumerate(report.news.upcoming_catalysts):
            if event.event_at <= report.generated_at + timedelta(days=policy.catalyst_horizon_days):
                add(
                    "near_term_catalyst",
                    "event",
                    "medium",
                    f"An unverified {event.category} event claim falls within "
                    f"{policy.catalyst_horizon_days} days ({event.certainty}).",
                    f"/news/upcoming_catalysts/{index}",
                )
    order = {"high": 0, "medium": 1, "info": 2}
    return sorted(findings, key=lambda item: (order[item.severity], item.category, item.code))
