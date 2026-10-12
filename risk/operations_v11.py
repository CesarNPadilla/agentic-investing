"""Synthetic operational reset preconditions and monotonic monitoring deadlines."""
from datetime import date, datetime
from typing import Literal
from zoneinfo import ZoneInfo

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, StrictBool

from risk.sleeve_v11 import Nonnegative


class SyntheticDailyResetEvidence(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    evidence_class: Literal["SYNTHETIC_ONLY"] = "SYNTHETIC_ONLY"
    latch_reasons: tuple[str, ...]
    breach_new_york_day: date
    next_trading_day: date
    calendar_verified: StrictBool = False
    designated_owner_id: str = Field(min_length=1)
    approving_human_id: str = Field(min_length=1)
    authentication_source: Literal["EXTERNAL_SYNTHETIC_VERIFIER", "AGENT_RUNTIME"]
    authentication_verified: StrictBool = False
    reconciled_at: AwareDatetime
    reconciliation_complete: StrictBool = False
    no_independent_hard_stop: StrictBool = False
    approved_at: AwareDatetime
    explicit_human_approval: StrictBool = False
    approval_nonce: str = Field(min_length=1)
    nonce_unused: StrictBool = False


class ResetDiagnostic(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    synthetic_reset_preconditions_passed: bool
    reason_codes: tuple[str, ...]
    reset_performed: Literal[False] = False
    human_authentication_production_verified: Literal[False] = False
    execution_available: Literal[False] = False


def check_synthetic_daily_reset(evidence: SyntheticDailyResetEvidence, *, now: datetime):
    if now.tzinfo is None or now.utcoffset() is None:
        raise ValueError("Aware clock required")
    reasons = []
    if not evidence.latch_reasons or set(evidence.latch_reasons)-{"ACCOUNT_DAILY_LOSS", "SLEEVE_DAILY_LOSS"}:
        reasons.append("INDEPENDENT_LATCH_NOT_RESETTABLE")
    if (not evidence.calendar_verified or evidence.next_trading_day <= evidence.breach_new_york_day
            or now.astimezone(ZoneInfo("America/New_York")).date() < evidence.next_trading_day):
        reasons.append("NEXT_TRADING_DAY_UNVERIFIED")
    if (not evidence.reconciliation_complete or evidence.reconciled_at > now
            or evidence.reconciled_at.astimezone(ZoneInfo("America/New_York")).date() < evidence.next_trading_day
            or (now-evidence.reconciled_at).total_seconds() > 60):
        reasons.append("FRESH_RECONCILIATION_REQUIRED")
    if (evidence.approved_at < evidence.reconciled_at or evidence.approved_at > now
            or not evidence.explicit_human_approval):
        reasons.append("ORDERED_HUMAN_APPROVAL_REQUIRED")
    if (evidence.authentication_source != "EXTERNAL_SYNTHETIC_VERIFIER"
            or not evidence.authentication_verified
            or evidence.designated_owner_id != evidence.approving_human_id):
        reasons.append("EXTERNAL_OWNER_AUTHENTICATION_REQUIRED")
    if not evidence.no_independent_hard_stop:
        reasons.append("INDEPENDENT_HARD_STOP")
    if not evidence.nonce_unused:
        reasons.append("APPROVAL_REPLAY")
    return ResetDiagnostic(synthetic_reset_preconditions_passed=not reasons, reason_codes=tuple(reasons))


class MonitoringInput(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    timer_seconds: int = Field(default=1, ge=1, le=5, strict=True)
    now_monotonic: Nonnegative
    last_completed_check_monotonic: Nonnegative | None = None
    open_orders: int = Field(ge=0, strict=True)
    open_positions: int = Field(ge=0, strict=True)
    event: Literal["FILL", "ORDER", "TIMER", "IDLE"] = "IDLE"


class MonitoringDiagnostic(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    check_due: bool
    fail_closed_required: bool
    reason_codes: tuple[str, ...]
    execution_available: Literal[False] = False


def monitoring_deadline(data: MonitoringInput):
    reasons = []
    active = data.open_orders > 0 or data.open_positions > 0
    elapsed = (data.now_monotonic-data.last_completed_check_monotonic
               if data.last_completed_check_monotonic is not None else None)
    if elapsed is not None and elapsed < 0:
        return MonitoringDiagnostic(check_due=True, fail_closed_required=True,
                                    reason_codes=("MONOTONIC_CLOCK_REGRESSION",))
    event_due = data.event in {"FILL", "ORDER"}
    timer_due = active and (elapsed is None or elapsed >= data.timer_seconds)
    overdue = active and (elapsed is None or elapsed > data.timer_seconds)
    if event_due:
        reasons.append("ORDER_OR_FILL_EVENT")
    if timer_due:
        reasons.append("ACTIVE_SCOPE_TIMER")
    if overdue:
        reasons.append("MONITORING_DEADLINE_MISSED")
    return MonitoringDiagnostic(check_due=event_due or timer_due, fail_closed_required=overdue,
                                reason_codes=tuple(reasons))
