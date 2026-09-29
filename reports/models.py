from datetime import UTC, datetime
from typing import Literal
from uuid import UUID, uuid4

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field

from fundamentals.analysis import FundamentalAnalysis
from market_data.models import Quote, Symbol
from news.analysis import NewsAnalysis
from portfolio.exposure import PortfolioExposure
from reports.assessment import ResearchAssessment
from risk.models import RiskFinding, RiskPolicy
from technical.history import PriceHistory, TechnicalSummary


class ResearchReport(BaseModel):
    model_config = ConfigDict(extra="forbid")
    schema_version: Literal["1", "2", "3", "4"] = "4"
    analysis_version: str | None = None
    portfolio: PortfolioExposure | None = None
    risk_policy: RiskPolicy = Field(default_factory=RiskPolicy)
    risk_findings: list[RiskFinding] = Field(default_factory=list)
    assessment: ResearchAssessment | None = None
    fundamentals: FundamentalAnalysis | None = None
    news: NewsAnalysis | None = None
    price_history: PriceHistory | None = None
    technicals: TechnicalSummary | None = None
    id: UUID = Field(default_factory=uuid4)
    symbol: Symbol
    generated_at: AwareDatetime = Field(default_factory=lambda: datetime.now(UTC))
    mode: Literal["research"] = "research"
    status: Literal["partial"] = "partial"
    quote: Quote
    summary: str
    bull_case: list[str] = Field(default_factory=list)
    bear_case: list[str] = Field(default_factory=list)
    catalysts: list[str] = Field(default_factory=list)
    technical_state: str = "unavailable"
    risks: list[str] = Field(default_factory=list)
    missing_data: list[str] = Field(default_factory=list)
