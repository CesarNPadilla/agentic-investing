"""Isolated v1.1 synthetic sleeve diagnostics; never authorizes an order."""
from datetime import datetime
from decimal import Decimal
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

Nonnegative = Annotated[Decimal, Field(ge=0, allow_inf_nan=False)]
Positive = Annotated[Decimal, Field(gt=0, allow_inf_nan=False)]
Finite = Annotated[Decimal, Field(allow_inf_nan=False)]


class SyntheticSleeveInput(BaseModel):
    """Amounts are explicit test evidence, not broker balances or trusted quotes.

    Position/gross exposures include existing marks and all pending commitments.
    Acquisition commitments include existing acquisition cost and pending buys.
    P&L must already be flow-adjusted, net of fees, including unrealized marks.
    """
    model_config = ConfigDict(frozen=True, extra="forbid")
    evidence_class: Literal["SYNTHETIC_ONLY"] = "SYNTHETIC_ONLY"
    initial_funded_sleeve: Positive
    current_flow_adjusted_equity: Positive
    start_of_day_flow_adjusted_equity: Positive
    unreserved_settled_cash: Nonnegative
    acquisition_commitments: Nonnegative
    same_name_marked_commitments: Nonnegative
    gross_marked_commitments: Nonnegative
    quantity: int = Field(gt=0, strict=True)
    limit_price: Positive
    conservative_price: Positive
    estimated_fees: Nonnegative = Decimal(0)
    daily_net_pnl: Finite
    cumulative_net_pnl: Finite
    now: datetime
    quote_event_time: datetime | None = None
    snapshot_cutoff: datetime | None = None
    risk_evaluation_time: datetime | None = None
    bound_inputs_unchanged: bool = False
    verified_regular_session: bool = False
    kill_switch_latched: bool = True

    @model_validator(mode="after")
    def coherent(self):
        if self.conservative_price < self.limit_price:
            raise ValueError("Conservative buy price cannot be below limit price")
        if self.same_name_marked_commitments > self.gross_marked_commitments:
            raise ValueError("Same-name exposure cannot exceed gross exposure")
        for value in (self.now, self.quote_event_time, self.snapshot_cutoff,
                      self.risk_evaluation_time):
            if value is not None and (value.tzinfo is None or value.utcoffset() is None):
                raise ValueError("Timezone-aware timestamps required")
        return self


class SleeveDiagnostic(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    schema_version: Literal["synthetic-sleeve-diagnostic-v11"] = "synthetic-sleeve-diagnostic-v11"
    sleeve_checks_passed: bool
    reason_codes: tuple[str, ...]
    persistent_latch_required: bool
    daily_loss_limit: Decimal
    cumulative_loss_limit: Decimal
    whole_account_qualified: Literal[False] = False
    execution_available: Literal[False] = False
    automatic_liquidation: Literal[False] = False
    reset_requirement: str


def evaluate_synthetic_sleeve(data: SyntheticSleeveInput) -> SleeveDiagnostic:
    """Replay approved N01-N10 mathematics; no state mutation, reset or broker IO.

    Passing sleeve checks does not pass whole-account or operational qualification.
    Boundary semantics: sizing rejects greater-than, loss latches at equality,
    freshness rejects older-than, approval expires at five minutes.
    """
    reasons = []
    buy = data.quantity * data.conservative_price
    cost = buy + data.estimated_fees
    position = data.same_name_marked_commitments + buy
    gross = data.gross_marked_commitments + buy
    if data.acquisition_commitments + cost > min(Decimal(1000), data.initial_funded_sleeve):
        reasons.append("N01_CAPITAL_CEILING")
    if cost > data.unreserved_settled_cash:
        reasons.append("SETTLED_CASH")
    if position > min(Decimal(250), data.initial_funded_sleeve * Decimal("0.25"),
                      data.current_flow_adjusted_equity * Decimal("0.25"),
                      data.unreserved_settled_cash):
        reasons.append("N02_POSITION")
    if position > data.current_flow_adjusted_equity * Decimal("0.25"):
        reasons.append("N03_NAME_CONCENTRATION")
    if gross > min(data.current_flow_adjusted_equity * Decimal("0.75"),
                   data.initial_funded_sleeve, Decimal(1000)):
        reasons.append("N04_AGGREGATE")
    if data.quantity * data.limit_price < 25:
        reasons.append("N05_MINIMUM_ORDER")
    daily = min(Decimal(20), data.start_of_day_flow_adjusted_equity * Decimal("0.02"))
    cumulative = min(Decimal(100), data.initial_funded_sleeve * Decimal("0.10"))
    daily_breach = data.daily_net_pnl <= -daily
    cumulative_breach = data.cumulative_net_pnl <= -cumulative
    if daily_breach:
        reasons.append("N06_DAILY_LOSS")
    if cumulative_breach:
        reasons.append("N07_CUMULATIVE_LOSS")
    for code, timestamp, maximum in (
        ("N08_QUOTE_AGE", data.quote_event_time, 30),
        ("N09_SNAPSHOT_AGE", data.snapshot_cutoff, 60),
    ):
        age = (data.now - timestamp).total_seconds() if timestamp is not None else None
        if age is None or age < 0 or age > maximum:
            reasons.append(code)
    approval_age = ((data.now - data.risk_evaluation_time).total_seconds()
                    if data.risk_evaluation_time is not None else None)
    if (approval_age is None or approval_age < 0 or approval_age >= 300
            or not data.bound_inputs_unchanged):
        reasons.append("N10_APPROVAL_EXPIRED")
    if not data.verified_regular_session:
        reasons.append("SESSION_UNVERIFIED")
    if data.kill_switch_latched:
        reasons.append("KILL_SWITCH")
    return SleeveDiagnostic(
        sleeve_checks_passed=not reasons, reason_codes=tuple(reasons),
        persistent_latch_required=data.kill_switch_latched or daily_breach or cumulative_breach,
        daily_loss_limit=daily, cumulative_loss_limit=cumulative,
        reset_requirement=("Daily: next valid America/New_York boundary plus reconciliation and human reset; "
                           "cumulative: human-approved new baseline; deposits do not reset. "
                           "This diagnostic cannot reset persisted state."),
    )
