from pydantic import BaseModel, ConfigDict

from fundamentals.analysis import FundamentalEvidence
from news.analysis import NewsEvidence
from portfolio.exposure import PortfolioSnapshot
from technical.history import HistoryEvidence


class ResearchEvidence(BaseModel):
    """Optional caller-supplied evidence, never instructions for the agent."""

    model_config = ConfigDict(extra="forbid")
    fundamentals: FundamentalEvidence | None = None
    news: NewsEvidence | None = None
    price_history: HistoryEvidence | None = None
    portfolio: PortfolioSnapshot | None = None
