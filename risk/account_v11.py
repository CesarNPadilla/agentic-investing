"""Isolated synthetic whole-account percentage diagnostics; no activation."""
from datetime import datetime, time
from decimal import Decimal
from typing import Literal
from zoneinfo import ZoneInfo

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, model_validator

from risk.loss_accounting_v11 import ExternalFlow
from risk.sleeve_v11 import Finite, Nonnegative, Positive


class SyntheticAccountInput(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    evidence_class: Literal["SYNTHETIC_ONLY"] = "SYNTHETIC_ONLY"
    day_baseline_at: AwareDatetime
    start_of_day_total_equity: Positive
    as_of: AwareDatetime
    current_total_equity: Finite
    external_flows: tuple[ExternalFlow, ...] = ()
    gross_marked_positions: Nonnegative
    gross_pending_buys: Nonnegative
    security_marked_position: Nonnegative
    security_pending_buys: Nonnegative
    quantity: int = Field(gt=0, strict=True)
    conservative_price: Positive
    estimated_fees: Nonnegative = Decimal(0)
    unreserved_settled_cash: Nonnegative
    all_holdings_and_orders_complete: bool = False
    ledger_marks_and_fees_reconciled: bool = False
    day_boundary_verified: bool = False
    kill_switch_latched: bool = True

    @model_validator(mode="after")
    def coherent(self):
        if self.day_baseline_at > self.as_of:
            raise ValueError("Baseline is after snapshot")
        zone = ZoneInfo("America/New_York")
        start, cutoff = self.day_baseline_at.astimezone(zone), self.as_of.astimezone(zone)
        if start.time() != time(0) or start.date() != cutoff.date():
            raise ValueError("Baseline must be midnight of the snapshot's New York calendar day")
        if (self.security_marked_position > self.gross_marked_positions
                or self.security_pending_buys > self.gross_pending_buys):
            raise ValueError("Security exposure exceeds aggregate exposure")
        if len({f.flow_id for f in self.external_flows}) != len(self.external_flows):
            raise ValueError("Duplicate external flow")
        if any(not self.day_baseline_at < f.posted_at <= self.as_of for f in self.external_flows):
            raise ValueError("Flow outside daily baseline interval")
        return self


class AccountDiagnostic(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    account_checks_passed: bool
    reason_codes: tuple[str, ...]
    daily_net_pnl: Decimal | None = None
    daily_loss_limit: Decimal
    gross_exposure_limit: Decimal | None = None
    security_exposure_limit: Decimal | None = None
    projected_gross_exposure: Decimal
    projected_security_exposure: Decimal
    existing_security_breach: bool
    daily_loss_breach: bool = False
    human_review_required: bool = False
    execution_available: Literal[False] = False
    production_trusted: Literal[False] = False
    automatic_liquidation: Literal[False] = False


def evaluate_synthetic_account(data: SyntheticAccountInput, *, now: datetime):
    if now.tzinfo is None or now.utcoffset() is None:
        raise ValueError("Aware evaluation time required")
    reasons = []
    age = (now-data.as_of).total_seconds()
    if age < 0 or age > 60:
        reasons.append("ACCOUNT_SNAPSHOT_TIME")
    if not data.all_holdings_and_orders_complete or not data.ledger_marks_and_fees_reconciled:
        reasons.append("ACCOUNT_EVIDENCE_INCOMPLETE")
    if not data.day_boundary_verified:
        reasons.append("ACCOUNT_DAY_BOUNDARY_UNVERIFIED")
    daily_limit = data.start_of_day_total_equity*Decimal("0.01")
    buy = data.quantity*data.conservative_price
    gross = data.gross_marked_positions+data.gross_pending_buys+buy
    name = data.security_marked_position+data.security_pending_buys+buy
    pnl = None
    if not reasons:
        pnl = (data.current_total_equity-data.start_of_day_total_equity
               -sum((f.amount for f in data.external_flows), Decimal(0)))
    breach = pnl is not None and pnl <= -daily_limit
    if breach:
        reasons.append("ACCOUNT_DAILY_LOSS")
    positive = data.current_total_equity > 0
    gross_limit = data.current_total_equity if positive else None
    name_limit = data.current_total_equity*Decimal("0.10") if positive else None
    existing_breach = positive and data.security_marked_position > name_limit
    if not positive:
        reasons.append("ACCOUNT_NONPOSITIVE_EQUITY")
    else:
        if gross > gross_limit:
            reasons.append("ACCOUNT_GROSS_EXPOSURE")
        if name > name_limit:
            reasons.append("ACCOUNT_SECURITY_CONCENTRATION")
        if existing_breach:
            reasons.append("EXISTING_SECURITY_BREACH_BLOCK_NEW_BUY")
    if buy+data.estimated_fees > data.unreserved_settled_cash:
        reasons.append("ACCOUNT_SETTLED_CASH")
    if data.kill_switch_latched:
        reasons.append("KILL_SWITCH")
    return AccountDiagnostic(account_checks_passed=not reasons, reason_codes=tuple(reasons),
        daily_net_pnl=pnl, daily_loss_limit=daily_limit, gross_exposure_limit=gross_limit,
        security_exposure_limit=name_limit, projected_gross_exposure=gross,
        projected_security_exposure=name, existing_security_breach=existing_breach,
        daily_loss_breach=breach, human_review_required=existing_breach or breach)
