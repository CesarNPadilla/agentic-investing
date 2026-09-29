"""Deterministic analysis of explicitly supplied, comparable financial statements."""

from datetime import date, datetime
from decimal import Decimal
from typing import Annotated, Protocol

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, HttpUrl, model_validator

from market_data.models import Symbol

Number = Annotated[Decimal, Field(allow_inf_nan=False)]
Nonnegative = Annotated[Number, Field(ge=0)]


class Statement(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    period_start: date
    period_end: date
    filed_at: AwareDatetime
    source_url: HttpUrl
    revenue: Nonnegative | None = None
    net_income: Number | None = None
    operating_cash_flow: Number | None = None
    capital_expenditures: Nonnegative | None = None
    current_assets: Nonnegative | None = None
    current_liabilities: Nonnegative | None = None
    total_debt: Nonnegative | None = None
    cash: Nonnegative | None = None
    equity: Number | None = None

    @model_validator(mode="after")
    def validate_period(self):
        if self.period_start > self.period_end:
            raise ValueError("Statement period start must precede its end")
        if self.filed_at.date() < self.period_end:
            raise ValueError("Filing must not precede the statement period end")
        return self


class FundamentalEvidence(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    symbol: Symbol
    source: str = Field(min_length=1, max_length=200)
    retrieved_at: AwareDatetime
    currency: str = Field(pattern=r"^[A-Z]{3}$")
    is_sample: bool = False
    current: Statement
    previous: Statement | None = None

    @model_validator(mode="after")
    def validate_comparison(self):
        if self.current.filed_at > self.retrieved_at:
            raise ValueError("Evidence retrieval must not precede filing")
        if self.previous:
            if self.previous.filed_at > self.retrieved_at:
                raise ValueError("Evidence retrieval must not precede filing")
            gap = (self.current.period_end - self.previous.period_end).days
            duration = (self.current.period_end - self.current.period_start).days
            prior_duration = (self.previous.period_end - self.previous.period_start).days
            if not 350 <= gap <= 380 or abs(duration - prior_duration) > 10:
                raise ValueError("Comparison requires matching year-over-year fiscal periods")
            if self.previous.period_end >= self.current.period_start:
                raise ValueError("Comparison periods must not overlap")
        return self


class FundamentalProvider(Protocol):
    def get_fundamentals(self, symbol: str) -> FundamentalEvidence: ...


class FundamentalAnalysis(BaseModel):
    model_config = ConfigDict(extra="forbid")
    evidence: FundamentalEvidence
    revenue_growth: Decimal | None = None
    net_margin: Decimal | None = None
    free_cash_flow: Decimal | None = None
    current_ratio: Decimal | None = None
    debt_to_equity: Decimal | None = None
    net_debt: Decimal | None = None
    missing_metrics: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


def analyze(evidence: FundamentalEvidence, now: datetime) -> FundamentalAnalysis:
    current = evidence.current
    result = FundamentalAnalysis(evidence=evidence)
    future = evidence.retrieved_at > now or current.filed_at > now
    if future:
        result.warnings.append("Fundamental evidence is future-dated; calculations omitted.")
    else:
        if evidence.previous and evidence.previous.revenue and current.revenue is not None:
            result.revenue_growth = current.revenue / evidence.previous.revenue - 1
        if current.revenue and current.net_income is not None:
            result.net_margin = current.net_income / current.revenue
        if current.operating_cash_flow is not None and current.capital_expenditures is not None:
            result.free_cash_flow = current.operating_cash_flow - current.capital_expenditures
        if current.current_liabilities and current.current_assets is not None:
            result.current_ratio = current.current_assets / current.current_liabilities
        if current.equity is not None and current.equity > 0 and current.total_debt is not None:
            result.debt_to_equity = current.total_debt / current.equity
        if current.total_debt is not None and current.cash is not None:
            result.net_debt = current.total_debt - current.cash
    result.missing_metrics = [
        name
        for name in (
            "revenue_growth",
            "net_margin",
            "free_cash_flow",
            "current_ratio",
            "debt_to_equity",
            "net_debt",
        )
        if getattr(result, name) is None
    ]
    if result.missing_metrics:
        result.warnings.append(
            "Some fundamental metrics lack usable inputs or positive denominators."
        )
    if (now.date() - current.period_end).days > 150:
        result.warnings.append("Financial period ended over 150 days ago; check for newer filings.")
    if (now - evidence.retrieved_at).days > 7:
        result.warnings.append("Fundamental evidence was retrieved over seven days ago.")
    if evidence.is_sample:
        result.warnings.append("Synthetic fundamental evidence; not investment evidence.")
    return result
