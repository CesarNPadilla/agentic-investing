"""Read-only capabilities; live adapters must validate provenance at ingestion."""

from typing import Protocol

from agents.long_term.models import Claim, FundamentalData, Metric, Source
from fundamentals.analysis import FundamentalProvider, analyze
from market_data.base import MarketDataProvider
from news.analysis import NewsProvider
from portfolio.intelligence import SecurityReference

__all__ = [
    "FundamentalDataProvider",
    "MarketDataProvider",
    "NewsProvider",
    "ReferenceDataProvider",
    "StatementProviderAdapter",
]


class FundamentalDataProvider(Protocol):
    def get_fundamentals(self, symbol: str) -> FundamentalData: ...


class ReferenceDataProvider(Protocol):
    def get_reference(self, symbol: str) -> SecurityReference: ...


class StatementProviderAdapter:
    """Reuse existing comparable-statement analysis without inventing additional KPIs."""

    def __init__(self, provider: FundamentalProvider, *, trusted_source=False):
        self.provider = provider
        self.trusted_source = trusted_source

    def get_fundamentals(self, symbol: str) -> FundamentalData:
        evidence = self.provider.get_fundamentals(symbol)
        analysis = analyze(evidence, evidence.retrieved_at)
        sources, metrics = [], []
        for label, statement in (("current", evidence.current), ("previous", evidence.previous)):
            if statement is None:
                continue
            source_id = f"statement:{label}"
            sources.append(
                Source(
                    source_id=source_id,
                    symbol=evidence.symbol,
                    source=evidence.source,
                    source_type="other",
                    published_at=statement.filed_at,
                    retrieved_at=evidence.retrieved_at,
                    period_start=statement.period_start,
                    period_end=statement.period_end,
                    relevant_claim="Reported financial statement",
                    url=str(statement.source_url),
                    reliable=self.trusted_source,
                    is_sample=evidence.is_sample,
                    historical=label == "previous",
                )
            )
            duration = (statement.period_end - statement.period_start).days
            basis = "quarter" if duration < 110 else "annual" if duration > 350 else None
            if basis is None:
                continue  # No silent treatment of YTD figures as quarterly or annual.
            for name in (
                "revenue",
                "net_income",
                "operating_cash_flow",
                "capital_expenditures",
                "cash",
                "total_debt",
            ):
                value = getattr(statement, name)
                if value is not None:
                    metrics.append(
                        Metric(
                            name=name,
                            value=value,
                            unit=evidence.currency,
                            source_id=source_id,
                            period_start=statement.period_start,
                            period_end=statement.period_end,
                            basis=basis,
                        )
                    )
        claims = {}
        for category, names in {
            "growth_context": ("revenue_growth",),
            "profitability_context": ("net_margin",),
            "cash_generation": ("free_cash_flow",),
            "financial_health": ("current_ratio", "net_debt", "debt_to_equity"),
        }.items():
            claims[category] = tuple(
                Claim(
                    text=f"{name}: {getattr(analysis, name)}",
                    evidence_references=("statement:current", "statement:previous")
                    if name == "revenue_growth"
                    else ("statement:current",),
                    kind="fact",
                )
                for name in names
                if getattr(analysis, name) is not None
            )
        return FundamentalData(
            symbol=evidence.symbol,
            retrieved_at=evidence.retrieved_at,
            sources=tuple(sources),
            metrics=tuple(metrics),
            claims=claims,
        )
