"""Explicit synthetic sleeve baselines and external-flow-adjusted loss evidence."""
from datetime import datetime
from decimal import Decimal
from typing import Literal
from zoneinfo import ZoneInfo

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, model_validator

from risk.sleeve_v11 import Finite, Positive


class ExternalFlow(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    flow_id: str = Field(min_length=1)
    posted_at: AwareDatetime
    amount: Finite  # Positive deposit; negative withdrawal, no internal transfers.


class SyntheticLossEvidence(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    evidence_class: Literal["SYNTHETIC_ONLY"] = "SYNTHETIC_ONLY"
    baseline_id: str = Field(min_length=1)
    baseline_at: AwareDatetime
    initial_funded_equity: Positive = Field(le=1000)
    daily_baseline_at: AwareDatetime
    daily_baseline_marked_equity: Finite
    as_of: AwareDatetime
    current_marked_equity: Finite
    flows: tuple[ExternalFlow, ...] = ()
    ledger_complete: bool = False
    marks_reconciled: bool = False
    fees_included_in_equity: bool = False
    daily_boundary_verified: bool = False

    @model_validator(mode="after")
    def coherent(self):
        if not self.baseline_at <= self.daily_baseline_at <= self.as_of:
            raise ValueError("Baseline/snapshot ordering invalid")
        if self.daily_baseline_at.astimezone(ZoneInfo("America/New_York")).date() != self.as_of.astimezone(ZoneInfo("America/New_York")).date():
            raise ValueError("Daily baseline must identify snapshot's New York day")
        if self.daily_baseline_at == self.baseline_at and self.daily_baseline_marked_equity != self.initial_funded_equity:
            raise ValueError("Initial baseline equity mismatch")
        if len({f.flow_id for f in self.flows}) != len(self.flows):
            raise ValueError("Duplicate external-flow identity")
        if any(not self.baseline_at < f.posted_at <= self.as_of for f in self.flows):
            raise ValueError("External flow outside baseline interval")
        if any(a.posted_at > b.posted_at for a, b in zip(self.flows, self.flows[1:])):
            raise ValueError("External flows must be ordered")
        return self


class LossAccountingDiagnostic(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    accounting_available: bool
    reason_codes: tuple[str, ...]
    daily_net_pnl: Decimal | None = None
    cumulative_net_pnl: Decimal | None = None
    current_flow_adjusted_equity: Decimal | None = None
    start_of_day_flow_adjusted_equity: Decimal | None = None
    daily_loss_limit: Decimal | None = None
    cumulative_loss_limit: Decimal | None = None
    persistent_latch_required: bool = False
    execution_available: Literal[False] = False


def calculate_synthetic_loss(evidence: SyntheticLossEvidence, *, now: datetime):
    if now.tzinfo is None or now.utcoffset() is None:
        raise ValueError("Aware evaluation time required")
    reasons = []
    if not (evidence.ledger_complete and evidence.marks_reconciled and evidence.fees_included_in_equity):
        reasons.append("LOSS_EVIDENCE_INCOMPLETE")
    if not evidence.daily_boundary_verified:
        reasons.append("DAILY_BOUNDARY_UNVERIFIED")
    age = (now-evidence.as_of).total_seconds()
    if age < 0 or age > 60:
        reasons.append("LOSS_SNAPSHOT_TIME")
    if reasons:
        return LossAccountingDiagnostic(accounting_available=False, reason_codes=tuple(reasons))
    flows = sum((f.amount for f in evidence.flows), Decimal(0))
    before_day = sum((f.amount for f in evidence.flows if f.posted_at <= evidence.daily_baseline_at), Decimal(0))
    adjusted_current = evidence.current_marked_equity-flows
    adjusted_start = evidence.daily_baseline_marked_equity-before_day
    daily = adjusted_current-adjusted_start
    cumulative = adjusted_current-evidence.initial_funded_equity
    cumulative_limit = min(Decimal(100), evidence.initial_funded_equity*Decimal("0.10"))
    daily_limit = min(Decimal(20), adjusted_start*Decimal("0.02")) if adjusted_start > 0 else None
    breached = cumulative <= -cumulative_limit or (daily_limit is not None and daily <= -daily_limit)
    if adjusted_start <= 0 or adjusted_current <= 0:
        reasons.append("NONPOSITIVE_ADJUSTED_EQUITY")
    return LossAccountingDiagnostic(accounting_available=not reasons, reason_codes=tuple(reasons),
        daily_net_pnl=daily, cumulative_net_pnl=cumulative, current_flow_adjusted_equity=adjusted_current,
        start_of_day_flow_adjusted_equity=adjusted_start, daily_loss_limit=daily_limit,
        cumulative_loss_limit=cumulative_limit, persistent_latch_required=breached)
