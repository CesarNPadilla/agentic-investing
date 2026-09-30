"""Serializable, versioned experiment contracts; no execution authorization."""

import itertools
from datetime import date
from decimal import Decimal
from typing import Literal
from zoneinfo import ZoneInfo

from pydantic import AwareDatetime, Field, model_validator

from market_data.models import Symbol
from portfolio.state import Identifier, Nonnegative, Record
from risk.policy import InvestmentPolicy
from strategies.models import StrategyVersion


class ExecutionAssumptions(Record):
    timing: Literal["next_session_close"] = "next_session_close"
    commission_fixed: Nonnegative = Decimal(0)
    commission_bps: Nonnegative = Decimal(0)
    slippage_bps: Decimal = Field(default=Decimal(5), ge=0, lt=5000)
    spread_bps: Decimal = Field(default=Decimal(0), ge=0, lt=5000)
    fractional_shares: bool = False
    cash_rule: Literal["no_borrowing_instant_simulated_settlement"] = (
        "no_borrowing_instant_simulated_settlement"
    )
    session_rule: Literal["supplied_exchange_closes"] = "supplied_exchange_closes"
    human_review: Literal["SKIP", "ASSUME_APPROVED_FOR_SIMULATION"] = "SKIP"
    max_exposure: Decimal = Field(default=Decimal(1), gt=0, le=1)
    max_position_value: Nonnegative | None = None


class Period(Record):
    role: Literal["development", "validation", "out_of_sample"]
    start: date
    end: date

    @model_validator(mode="after")
    def ordered(self):
        if self.start > self.end:
            raise ValueError("Reversed period")
        return self


class BacktestConfig(Record):
    schema_version: Literal["backtest-config-v1"] = "backtest-config-v1"
    backtest_id: Identifier
    strategy: StrategyVersion
    risk_policy: InvestmentPolicy
    start_date: date
    end_date: date
    initial_capital: Decimal = Field(gt=0, allow_inf_nan=False)
    capital_mode: Literal["STRATEGY_RESEARCH", "EXPERIMENTAL"] = "STRATEGY_RESEARCH"
    benchmark: Symbol = "VOO"
    benchmark_basis: Literal["price_return", "total_return"] = "total_return"
    security_universe: tuple[Symbol, ...] = Field(min_length=1)
    universe_scope: Literal["targeted", "broad"] = "targeted"
    evaluation_frequency: Literal["daily", "weekly", "monthly", "event_driven"] = "daily"
    execution: ExecutionAssumptions = ExecutionAssumptions()
    periods: tuple[Period, ...] = ()
    evaluated_role: Literal["development", "validation", "out_of_sample"] = "development"
    data_source_metadata: dict[str, str]
    created_at: AwareDatetime
    code_version: Identifier
    account_id: Identifier = "backtest"
    annual_sessions: int = Field(default=252, gt=0)
    annual_risk_free_rate: Decimal | None = Field(default=None, ge=0, lt=1)
    max_observation_age_seconds: int = Field(default=86400, gt=0)

    @model_validator(mode="after")
    def valid(self):
        if self.risk_policy.daily_loss_timezone:
            ZoneInfo(self.risk_policy.daily_loss_timezone)
        if self.start_date >= self.end_date:
            raise ValueError("Backtest needs an ordered multi-day interval")
        if len(set(self.security_universe)) != len(self.security_universe):
            raise ValueError("Duplicate universe symbol")
        if self.capital_mode == "EXPERIMENTAL" and self.initial_capital > 160:
            raise ValueError("Experimental starting capital exceeds USD 160")
        if self.periods:
            ordered = sorted(self.periods, key=lambda p: p.start)
            ranks = {"development": 0, "validation": 1, "out_of_sample": 2}
            if [ranks[p.role] for p in ordered] != sorted(ranks[p.role] for p in ordered):
                raise ValueError("Development must precede validation and holdout")
            if len({p.role for p in ordered}) != len(ordered):
                raise ValueError("Duplicate period role")
            if any(a.end >= b.start for a, b in itertools.pairwise(ordered)):
                raise ValueError("Development/validation/holdout periods overlap")
            selected = next((p for p in ordered if p.role == self.evaluated_role), None)
            if (
                selected is None
                or not selected.start <= self.start_date < self.end_date <= selected.end
            ):
                raise ValueError("Test interval outside selected period")
        return self


class ValidationGates(Record):
    max_drawdown: Decimal | None = Field(default=None, ge=0, le=1)
    minimum_observations: int | None = Field(default=None, gt=0)
    minimum_trades: int | None = Field(default=None, ge=0)
    max_turnover: Nonnegative | None = None
    acceptable_data_quality: tuple[str, ...] | None = None
    zero_lookahead_violations: Literal[True] = True
    zero_policy_bypasses: Literal[True] = True


class BacktestResult(Record):
    engine_version: Literal["backtesting-v0.1"] = "backtesting-v0.1"
    config: BacktestConfig
    dataset_digest: str
    input_digest: str
    status: Literal[
        "COMPLETED",
        "FAILED",
        "INVALID_DATA",
        "LOOKAHEAD_VIOLATION",
        "INSUFFICIENT_DATA",
        "POLICY_VIOLATION",
    ]
    metrics: dict = Field(default_factory=dict)
    equity_curve: tuple[dict, ...] = ()
    decisions: tuple[dict, ...] = ()
    trades: tuple[dict, ...] = ()
    data_quality: tuple[str, ...] = ()
    bias_warnings: tuple[str, ...] = ()
    lookahead_violations: int = 0
    policy_bypasses: Literal[0] = 0
    forward_paper_sessions: Literal[0] = 0
    required_forward_paper_sessions: Literal[60] = 60
    validation_status: Literal["NOT_EVALUATED"] = "NOT_EVALUATED"
    execution_available: Literal[False] = False


class StrategyValidationReport(Record):
    strategy_id: str
    strategy_version: str
    backtests_evaluated: tuple[str, ...]
    datasets: tuple[str, ...]
    time_periods: tuple[dict, ...]
    assumptions: tuple[dict, ...]
    performance: tuple[dict, ...]
    data_quality_findings: tuple[str, ...]
    bias_warnings: tuple[str, ...]
    gate_results: dict[str, str]
    validation_gates: ValidationGates
    unresolved_risks: tuple[str, ...]
    validation_status: Literal["NOT_EVALUATED", "PASS", "FAIL", "REQUIRES_REVIEW"]
    paper_eligibility: Literal[
        "NOT_ELIGIBLE", "REQUIRES_REVIEW", "ELIGIBLE_FOR_FORWARD_PAPER_VALIDATION"
    ]
    forward_paper_sessions: Literal[0] = 0
    required_forward_paper_sessions: Literal[60] = 60
    execution_available: Literal[False] = False
