"""Owner-configurable research policy. Safety boundaries cannot be configured away."""

from decimal import Decimal
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from market_data.models import Symbol

Money = Annotated[Decimal, Field(ge=0, allow_inf_nan=False)]


class InvestmentPolicy(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    version: Literal["investment-policy-v3"] = "investment-policy-v3"
    policy_revision: Literal["0.1"] = "0.1"
    analysis_scope: Literal["entire_portfolio"] = "entire_portfolio"
    auto_liquidate_existing_holdings: Literal[False] = False
    automatic_rebalancing: Literal[False] = False
    audit_trail_required: Literal[True] = True
    thesis_required: Literal[True] = True
    entry_thesis_required: Literal[True] = True
    exit_invalidation_thesis_required: Literal[True] = True
    concentration_warning: Decimal = Field(default=Decimal("0.20"), ge=0, le=1)
    severe_concentration_warning: Decimal = Field(default=Decimal("0.30"), ge=0, le=1)
    environment: Literal["research", "paper"] = "research"
    production_trading: Literal[False] = False
    automated_trading: Literal[False] = False
    human_approval_required: Literal[True] = True
    new_purchase_allowlist: frozenset[Symbol] = Field(
        default=frozenset({"AAPL", "MSFT", "SPY"}),
        json_schema_extra={"default": ["AAPL", "MSFT", "SPY"]},
    )
    # Independent from purchase permission; None permits holdings analysis only.
    research_universe: frozenset[Symbol] | None = Field(
        default=frozenset({"AAPL", "MSFT", "SPY"}),
        json_schema_extra={"default": ["AAPL", "MSFT", "SPY"]},
    )
    long_only: Literal[True] = True
    buy_only: Literal[True] = True
    margin_allowed: Literal[False] = False
    options_allowed: Literal[False] = False
    short_selling_allowed: Literal[False] = False
    leverage_allowed: Literal[False] = False
    fractional_orders_allowed: Literal[False] = False
    complex_orders_allowed: Literal[False] = False
    kill_switch_required: Literal[True] = True
    currency: Literal["USD"] = "USD"
    agent_experimental_capital_limit: Money | None = Field(default=Decimal(160), le=160)
    max_daily_loss: Money | None = None
    max_experimental_loss: Money | None = None
    max_position_exposure: Money | None = None
    max_concentration: Decimal | None = Field(default=None, ge=0, le=1, allow_inf_nan=False)
    max_state_age_seconds: int | None = Field(default=None, gt=0, strict=True)
    daily_loss_timezone: str | None = None
    objective: str | None = "Long-term capital growth"
    holding_horizon: str | None = "Long-term"
    benchmark: str | None = "VOO / S&P 500"
    benchmark_comparison: str = "VOO"
    rebalance_cadence: str | None = "Rule/event driven, not automatic"
    review_cadence: str | None = "Weekly"
    research_review_cadence: str = "Daily"
    strategy_rules: str | None = None

    @field_validator("new_purchase_allowlist")
    @classmethod
    def restricted_symbols(cls, value):
        if not value <= {"AAPL", "MSFT", "SPY"}:
            raise ValueError("Experimental universe cannot be expanded in this phase")
        return value

    @model_validator(mode="after")
    def warning_order(self):
        if self.concentration_warning >= self.severe_concentration_warning:
            raise ValueError("Severe concentration threshold must exceed warning threshold")
        return self

    def may_research(self, symbol: str, portfolio_holdings=()) -> bool:
        return symbol in (self.research_universe or ()) or any(
            holding.symbol == symbol and holding.quantity != 0 for holding in portfolio_holdings
        )
