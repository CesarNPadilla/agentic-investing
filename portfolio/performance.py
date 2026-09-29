"""Flow-adjusted performance from explicit, aligned total-return evidence only."""

from decimal import Decimal
from itertools import pairwise
from statistics import mean, stdev
from typing import Literal

from pydantic import AwareDatetime, Field

from portfolio.state import Number, Record


class PerformancePoint(Record):
    at: AwareDatetime
    equity: Decimal = Field(gt=0, allow_inf_nan=False)
    benchmark_total_return_index: Decimal = Field(gt=0, allow_inf_nan=False)
    external_flow: Number | None = None


class PerformanceEvidence(Record):
    source: str = Field(min_length=1)
    benchmark: Literal["VOO"] = "VOO"
    points: tuple[PerformancePoint, ...] = Field(max_length=10000)
    fully_adjusted: bool = False
    session_calendar_validated: bool = False
    flow_timing: Literal["period_start", "period_end"] | None = None
    periods_per_year: int | None = Field(default=None, gt=0)
    risk_free_return_per_period: Number | None = None


class PortfolioPerformance(Record):
    as_of: AwareDatetime
    status: Literal["AVAILABLE", "INSUFFICIENT_DATA"]
    reasons: tuple[str, ...] = ()
    history_start: AwareDatetime | None = None
    history_end: AwareDatetime | None = None
    portfolio_total_return: Decimal | None = None
    benchmark_total_return: Decimal | None = None
    excess_return: Decimal | None = None
    volatility_per_period: float | None = None
    annualized_volatility: float | None = None
    drawdown: Decimal | None = None
    maximum_drawdown: Decimal | None = None
    sharpe: float | None = None


def performance(evidence: PerformanceEvidence | None, *, as_of) -> PortfolioPerformance:
    reasons = []
    if evidence is None:
        return PortfolioPerformance(
            as_of=as_of, status="INSUFFICIENT_DATA", reasons=("performance_history_unset",)
        )
    points = evidence.points
    if len(points) < 2:
        reasons.append("insufficient_history")
    if not evidence.fully_adjusted or not evidence.session_calendar_validated:
        reasons.append("adjustments_or_calendar_unverified")
    if evidence.flow_timing is None or any(p.external_flow is None for p in points[1:]):
        reasons.append("cash_flow_evidence_missing")
    if any(p.at > as_of for p in points) or any(a.at >= b.at for a, b in pairwise(points)):
        reasons.append("future_or_misaligned_timestamps")
    if reasons:
        return PortfolioPerformance(as_of=as_of, status="INSUFFICIENT_DATA", reasons=tuple(reasons))
    growth, peak, maximum = Decimal(1), Decimal(1), Decimal(0)
    returns = []
    for previous, current in pairwise(points):
        denominator = (
            previous.equity + current.external_flow
            if evidence.flow_timing == "period_start"
            else previous.equity
        )
        numerator = (
            current.equity
            if evidence.flow_timing == "period_start"
            else current.equity - current.external_flow
        )
        if denominator <= 0 or numerator <= 0:
            return PortfolioPerformance(
                as_of=as_of, status="INSUFFICIENT_DATA", reasons=("invalid_flow_adjusted_equity",)
            )
        change = numerator / denominator - 1
        returns.append(float(change))
        growth *= 1 + change
        peak = max(peak, growth)
        maximum = max(maximum, 1 - growth / peak)
    portfolio_return = growth - 1
    benchmark_return = (
        points[-1].benchmark_total_return_index / points[0].benchmark_total_return_index - 1
    )
    volatility = stdev(returns) if len(returns) >= 2 else None
    factor = evidence.periods_per_year**0.5 if evidence.periods_per_year else None
    sharpe = (
        (mean(returns) - float(evidence.risk_free_return_per_period)) / volatility * factor
        if volatility and factor and evidence.risk_free_return_per_period is not None
        else None
    )
    return PortfolioPerformance(
        as_of=as_of,
        status="AVAILABLE",
        history_start=points[0].at,
        history_end=points[-1].at,
        portfolio_total_return=portfolio_return,
        benchmark_total_return=benchmark_return,
        excess_return=portfolio_return - benchmark_return,
        volatility_per_period=volatility,
        annualized_volatility=volatility * factor if volatility is not None and factor else None,
        drawdown=growth / peak - 1,
        maximum_drawdown=maximum,
        sharpe=sharpe,
    )
