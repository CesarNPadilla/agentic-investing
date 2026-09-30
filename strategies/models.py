"""Versioned, nonexecuting strategy and opportunity contracts."""

from decimal import Decimal
from typing import Literal

from pydantic import AwareDatetime, Field, model_serializer, model_validator

from agents.long_term.models import Freshness, ResearchConfig, ValuationContext
from market_data.models import Symbol
from portfolio.state import Identifier, Nonnegative, Record
from risk.proposals import TradeProposal
from strategies.experiment_models import DimensionCheck, ExperimentParameters

Domain = Literal["long_term", "swing"]
OpportunityType = Literal[
    "NEW_LONG_TERM_POSITION",
    "ADD_TO_EXISTING",
    "LONG_TERM_REVIEW",
    "THESIS_STRENGTHENING",
    "THESIS_WEAKENING",
    "CONCENTRATION_REVIEW",
    "VALUATION_REVIEW",
    "SWING_SETUP",
    "CATALYST_EVENT",
    "RISK_REDUCTION_REVIEW",
]


class EntryConfig(Record):
    max_research_age_seconds: int = Field(gt=0)
    min_evidence_sources: int = Field(default=1, gt=0)
    allow_test_data: bool = False
    source_freshness: ResearchConfig = ResearchConfig()
    # Explicit reviewed assessments, never inferred from sentiment or a universal score.
    valuation_decision: Literal["ACCEPTABLE", "UNATTRACTIVE", "UNSET"] = "UNSET"
    portfolio_fit_decision: Literal["ACCEPTABLE", "REDUNDANT", "UNSET"] = "UNSET"
    concentration_ceiling: Decimal | None = Field(default=None, gt=0, le=1)
    fixed_notional: Nonnegative | None = None


class SwingConfig(Record):
    parameters_status: Literal["UNSET", "REVIEWED_FOR_RESEARCH"] = "UNSET"
    fast_period: int | None = Field(default=None, gt=0)
    slow_period: int | None = Field(default=None, gt=0)
    stop_atr_multiple: Decimal | None = Field(default=None, gt=0, allow_inf_nan=False)
    profit_atr_multiple: Decimal | None = Field(default=None, gt=0, allow_inf_nan=False)
    max_holding_sessions: int | None = Field(default=None, gt=0)
    max_holding_days: int | None = Field(default=None, gt=0)
    risk_budget: Nonnegative | None = None
    max_notional: Nonnegative | None = None


class StrategyVersion(Record):
    strategy_id: Identifier
    strategy_version: Identifier
    strategy_domain: Domain
    configuration: EntryConfig
    swing: SwingConfig = SwingConfig()
    created_at: AwareDatetime
    authorization_reference: Identifier | None = None
    status: Literal["DEVELOPMENT", "BACKTEST", "PAPER", "RETIRED"] = "DEVELOPMENT"
    experiment: ExperimentParameters | None = None

    @model_validator(mode="after")
    def experiment_identity(self):
        named = {"LONG_TERM_QUALITY_GROWTH": "long_term", "SWING_TREND_MOMENTUM": "swing"}
        if (self.strategy_id in named or self.experiment is not None) and (
            self.experiment is None
            or self.strategy_id != self.experiment.hypothesis
            or self.strategy_domain != named.get(self.strategy_id)
            or self.status not in {"BACKTEST", "RETIRED"}
        ):
            raise ValueError("Named research experiments require matching BACKTEST definitions")
        return self

    @model_serializer(mode="wrap")
    def compatible_dump(self, handler):
        value = handler(self)
        if self.experiment is None:
            value.pop("experiment", None)
        return value


class InvestmentOpportunity(Record):
    schema_version: Literal["opportunity-v1"] = "opportunity-v1"
    opportunity_id: Identifier
    scope_id: Identifier
    symbol: Symbol
    timestamp: AwareDatetime
    opportunity_type: OpportunityType
    classifications: tuple[OpportunityType, ...]
    strategy_domain: Domain
    research_assessment_id: Identifier
    assessment_digest: Identifier
    thesis_reference: Identifier
    thesis_status: str
    portfolio_role: tuple[str, ...]
    security_roles: tuple[str, ...]
    current_allocation: Decimal | None
    opportunity_summary: str
    supporting_factors: tuple[str, ...]
    opposing_factors: tuple[str, ...]
    catalysts: tuple[str, ...]
    risks: tuple[str, ...]
    valuation_context: ValuationContext
    portfolio_fit: str
    concentration_impact: tuple[str, ...]
    investment_horizon: str
    data_quality: dict[str, Freshness]
    missing_data: tuple[str, ...]
    evidence_references: tuple[str, ...]
    uncertainty: tuple[str, ...]
    policy_checks: tuple[str, ...]
    opportunity_status: Literal[
        "IDENTIFIED",
        "UNDER_REVIEW",
        "STRATEGY_ELIGIBLE",
        "INSUFFICIENT_DATA",
        "REJECTED",
        "EXPIRED",
    ]
    execution_available: Literal[False] = False


class StrategyEvaluation(Record):
    status: Literal["RISK_REVIEW", "INSUFFICIENT_DATA", "REJECTED", "NO_ENTRY", "EXIT_REVIEW"]
    reasons: tuple[str, ...]
    proposal: TradeProposal | None = None
    execution_available: Literal[False] = False
    diagnostics: tuple[DimensionCheck, ...] = ()

    @model_serializer(mode="wrap")
    def compatible_dump(self, handler):
        value = handler(self)
        if not self.diagnostics:
            value.pop("diagnostics", None)
        return value
