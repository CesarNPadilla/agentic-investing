"""Versioned research contracts. Unknowns are null; conclusions reference evidence."""

from datetime import date
from decimal import Decimal
from typing import Literal
from uuid import uuid4

from pydantic import AwareDatetime, Field, model_validator

from market_data.models import Quote, Symbol
from news.analysis import NewsEvidence
from portfolio.state import Identifier, Number, Record

ThesisStatus = Literal[
    "STRONGER", "UNCHANGED", "WEAKER", "UNDER_REVIEW", "INVALIDATED", "INSUFFICIENT_DATA"
]
Category = Literal[
    "business_summary",
    "investment_thesis",
    "positive_drivers",
    "negative_drivers",
    "catalysts",
    "risks",
    "invalidation_conditions",
    "financial_health",
    "growth_context",
    "profitability_context",
    "competitive_position",
    "ai_exposure",
    "cash_generation",
]


class Source(Record):
    source_id: Identifier
    symbol: Symbol
    source: Identifier
    source_type: Literal[
        "sec", "investor_relations", "earnings_release", "market_data", "news", "other"
    ]
    published_at: AwareDatetime
    retrieved_at: AwareDatetime
    period_start: date | None = None
    period_end: date | None = None
    relevant_claim: Identifier
    url: str | None = None
    reliable: bool = False
    is_sample: bool = False
    historical: bool = False

    @model_validator(mode="after")
    def chronology(self):
        if self.published_at > self.retrieved_at:
            raise ValueError("Retrieval precedes publication")
        if self.period_start and (not self.period_end or self.period_start > self.period_end):
            raise ValueError("Invalid data period")
        if self.period_end and self.period_end > self.published_at.date():
            raise ValueError("Reported period follows publication")
        return self


class Claim(Record):
    text: Identifier
    evidence_references: tuple[Identifier, ...] = Field(min_length=1)
    kind: Literal["fact", "interpretation"] = "interpretation"


class Metric(Record):
    name: Identifier
    value: Number
    unit: Identifier
    source_id: Identifier
    period_start: date
    period_end: date
    basis: Literal["quarter", "annual", "ttm", "point_in_time", "forward"]

    @model_validator(mode="after")
    def period(self):
        if self.period_start > self.period_end:
            raise ValueError("Invalid metric period")
        return self


class FundamentalData(Record):
    symbol: Symbol
    retrieved_at: AwareDatetime
    sources: tuple[Source, ...] = ()
    metrics: tuple[Metric, ...] = ()
    # Descriptions are evidence claims, never policy or thesis-status instructions.
    claims: dict[Category, tuple[Claim, ...]] = Field(default_factory=dict)

    @model_validator(mode="after")
    def references(self):
        sources = {s.source_id: s for s in self.sources}
        if len(sources) != len(self.sources) or any(s.symbol != self.symbol for s in self.sources):
            raise ValueError("Duplicate source or mismatched symbol")
        if any(s.retrieved_at > self.retrieved_at for s in self.sources):
            raise ValueError("Source retrieval follows bundle retrieval")
        for metric in self.metrics:
            source = sources.get(metric.source_id)
            if source is None or (source.period_start, source.period_end) != (
                metric.period_start,
                metric.period_end,
            ):
                raise ValueError("Metric needs a source with matching period")
        keys = [(m.name, m.period_start, m.period_end, m.basis) for m in self.metrics]
        if len(keys) != len(set(keys)):
            raise ValueError("Duplicate metric period")
        for claims in self.claims.values():
            if any(not set(c.evidence_references) <= sources.keys() for c in claims):
                raise ValueError("Unknown claim evidence")
        return self


class Assumption(Record):
    """Reviewed configuration, never populated from publisher instructions."""

    name: Identifier
    metric: Identifier
    unit: Identifier
    basis: Literal["quarter", "annual", "ttm", "point_in_time", "forward"]
    operator: Literal["ge", "le"]
    threshold: Number
    invalidates_when_false: bool = False


class ResearchPlan(Record):
    plan_id: Identifier
    symbol: Symbol
    reviewed_by: Identifier
    reviewed_at: AwareDatetime
    thesis: Identifier
    assumptions: tuple[Assumption, ...] = Field(min_length=1)

    @model_validator(mode="after")
    def distinct(self):
        if len({a.name for a in self.assumptions}) != len(self.assumptions):
            raise ValueError("Duplicate assumption name")
        return self


class ResearchConfig(Record):
    # Research freshness heuristics, not execution risk-policy tolerances.
    market_max_age_hours: int = Field(default=24, gt=0)
    news_max_age_hours: int = Field(default=24, gt=0)
    retrieval_max_age_days: int = Field(default=7, gt=0)
    financial_period_max_age_days: int = Field(default=150, gt=0)
    valuation_max_age_days: int = Field(default=7, gt=0)
    incomplete_retry_hours: int = Field(default=24, gt=0)
    full_review_max_age_days: int = Field(default=90, gt=0)
    aliases: dict[Symbol, Symbol] = Field(default_factory=lambda: {"GOOG": "GOOGL"})
    comparison_symbols: tuple[Symbol, ...] = (
        "AAPL",
        "MSFT",
        "NVDA",
        "AMZN",
        "GOOGL",
        "META",
        "TSLA",
    )
    allow_test_data: bool = False

    @model_validator(mode="after")
    def no_alias_chains(self):
        if any(target in self.aliases for target in self.aliases.values()):
            raise ValueError("Alias chains and cycles are unsupported")
        return self


class Freshness(Record):
    state: Literal["CURRENT", "LATEST_REPORTED", "HISTORICAL", "STALE", "UNAVAILABLE"]
    as_of: AwareDatetime | None = None
    reason: str | None = None


class ValuationContext(Record):
    status: Literal["AVAILABLE", "INSUFFICIENT_DATA"] = "INSUFFICIENT_DATA"
    methods: tuple[Metric, ...] = ()
    conclusions: tuple[Claim, ...] = ()
    # Every metric retains its own period and source timestamp; no universal price target.


class PortfolioContext(Record):
    observation_id: str
    as_of: AwareDatetime
    actual_symbols: tuple[Symbol, ...]
    current_allocation: Decimal | None = None
    current_market_value: Decimal | None = None
    cost_basis: Decimal | None = None
    unrealized_pnl: Decimal | None = None
    classifications: tuple[str, ...] = ()
    concentration_flags: tuple[str, ...] = ()
    data_gaps: tuple[str, ...] = ()
    portfolio_overlap: str = "Direct holdings only; ETF look-through unknown"
    diversification_impact: str | None = None


class ResearchAssessment(Record):
    schema_version: Literal["long-term-research-v1"] = "long-term-research-v1"
    assessment_id: str = Field(default_factory=lambda: str(uuid4()))
    run_id: str
    scope_id: str
    symbol: Symbol
    timestamp: AwareDatetime
    research_horizon: str | None
    portfolio_role: tuple[str, ...] = ()
    thesis_reference: tuple[str, ...] = ()
    previous_assessment_id: str | None = None
    current_price: Decimal | None = None
    price_currency: str | None = None
    market_data_timestamp: AwareDatetime | None = None
    fundamental_data_timestamp: AwareDatetime | None = None
    business_summary: tuple[Claim, ...] = ()
    investment_thesis: str | None = None
    thesis_status: ThesisStatus = "INSUFFICIENT_DATA"
    thesis_changes: tuple[str, ...] = ()
    positive_drivers: tuple[Claim, ...] = ()
    negative_drivers: tuple[Claim, ...] = ()
    catalysts: tuple[Claim, ...] = ()
    risks: tuple[Claim, ...] = ()
    invalidation_conditions: tuple[str, ...] = ()
    valuation_context: ValuationContext = ValuationContext()
    financial_health: tuple[Claim, ...] = ()
    growth_context: tuple[Claim, ...] = ()
    profitability_context: tuple[Claim, ...] = ()
    competitive_position: tuple[Claim, ...] = ()
    ai_exposure: tuple[Claim, ...] = ()
    cash_generation: tuple[Claim, ...] = ()
    portfolio_fit: PortfolioContext | None = None
    concentration_impact: tuple[str, ...] = ()
    relevant_news: NewsEvidence | None = None
    data_sources: tuple[Source, ...] = ()
    data_quality: dict[str, Freshness] = Field(default_factory=dict)
    missing_data: tuple[str, ...] = ()
    uncertainty: tuple[str, ...] = ()
    agent_summary: str
    metrics: tuple[Metric, ...] = ()
    assumption_results: dict[str, bool | None] = Field(default_factory=dict)
    plan: ResearchPlan | None = None
    quote: Quote | None = None
    fundamental_data: FundamentalData | None = None
    reference_data: dict | None = None
    review_kind: Literal["baseline", "targeted", "quarterly"]
    execution_available: Literal[False] = False


class ResearchRun(Record):
    run_id: str
    agent: Literal["long-term-research-v0.1"] = "long-term-research-v0.1"
    timestamp: AwareDatetime
    scope_id: str
    symbol: Symbol
    status: Literal["STARTED", "COMPLETED", "FAILED", "SKIPPED"]
    inputs_used: tuple[str, ...] = ()
    input_snapshot: dict = Field(default_factory=dict)
    source_references: tuple[str, ...] = ()
    previous_thesis_state: str | None = None
    resulting_thesis_state: ThesisStatus | None = None
    material_changes: tuple[str, ...] = ()
    missing_information: tuple[str, ...] = ()
    errors: tuple[str, ...] = ()
    reasoning_summary: str = ""
    assessment_id: str | None = None
    execution_available: Literal[False] = False
