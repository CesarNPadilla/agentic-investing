"""Synthetic reset-review prerequisites; no production approval or state mutation."""

import hashlib
import json
from datetime import date, datetime
from typing import Literal
from zoneinfo import ZoneInfo

from pydantic import UUID4, AwareDatetime, BaseModel, ConfigDict, Field, StrictBool

from market_data.nyse_calendar import CalendarCoverageError
from security.webull_control_request import ControlRequest

Digest = str
NY = ZoneInfo("America/New_York")


class SyntheticResetContext(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    evidence_class: Literal["SYNTHETIC_ONLY"] = "SYNTHETIC_ONLY"
    account_binding_sha256: Digest = Field(pattern=r"^[0-9a-f]{64}$")
    state_sha256: Digest = Field(pattern=r"^[0-9a-f]{64}$")
    policy_sha256: Digest = Field(pattern=r"^[0-9a-f]{64}$")
    designated_credential_sha256: Digest = Field(pattern=r"^[0-9a-f]{64}$")
    breach_new_york_day: date
    latch_reasons: tuple[str, ...]
    reconciled_at: AwareDatetime
    reconciled_state_sha256: Digest = Field(pattern=r"^[0-9a-f]{64}$")
    reconciliation_complete: StrictBool = False
    source_contracts_qualified: StrictBool = False
    calendar_source_qualified: StrictBool = False
    no_independent_stop: StrictBool = False


class SyntheticOwnerApproval(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    evidence_class: Literal["SYNTHETIC_ONLY"] = "SYNTHETIC_ONLY"
    action: Literal["APPROVE_WEBULL_DAILY_LOSS_RESET"]
    approval_id: UUID4
    review_sha256: Digest = Field(pattern=r"^[0-9a-f]{64}$")
    credential_sha256: Digest = Field(pattern=r"^[0-9a-f]{64}$")
    approved_at: AwareDatetime
    external_signature_fixture_verified: StrictBool = False


def reset_review_digest(request: ControlRequest, context: SyntheticResetContext, calendar):
    descriptor = {
        "action": "APPROVE_WEBULL_DAILY_LOSS_RESET",
        "request": request.model_dump(mode="json"),
        "context": context.model_dump(mode="json"),
        "calendar_sha256": calendar.digest,
    }
    encoded = json.dumps(descriptor, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(encoded).hexdigest()


def evaluate_synthetic_reset_review(
    request: ControlRequest,
    context: SyntheticResetContext,
    *,
    calendar,
    now: datetime,
    approval: SyntheticOwnerApproval | None = None,
    used_approval_ids: frozenset[str] = frozenset(),
):
    if now.tzinfo is None or now.utcoffset() is None:
        raise ValueError("Aware controller clock required")
    reasons = []
    if request.action != "REQUEST_RESET_REVIEW":
        reasons.append("RESET_REVIEW_ACTION_REQUIRED")
    if request.account_binding_sha256 != context.account_binding_sha256:
        reasons.append("ACCOUNT_BINDING_CHANGED")
    if request.expected_state_sha256 != context.state_sha256:
        reasons.append("EXPECTED_STATE_CHANGED")
    if not context.latch_reasons or set(context.latch_reasons) - {
        "ACCOUNT_DAILY_LOSS",
        "SLEEVE_DAILY_LOSS",
    }:
        reasons.append("INDEPENDENT_LATCH_NOT_RESETTABLE")
    current_day = now.astimezone(NY).date()
    try:
        next_day = calendar.next_trading_day(context.breach_new_york_day)
        schedule_ok = current_day >= next_day and calendar.session(current_day) is not None
    except CalendarCoverageError:
        schedule_ok = False
    if not context.calendar_source_qualified or not schedule_ok:
        reasons.append("NEXT_NYSE_DAY_UNQUALIFIED")
    age = (now - context.reconciled_at).total_seconds()
    if (
        not context.reconciliation_complete
        or not 0 <= age <= 60
        or context.reconciled_at.astimezone(NY).date() != current_day
        or context.reconciled_state_sha256 != context.state_sha256
    ):
        reasons.append("FRESH_RECONCILIATION_REQUIRED")
    if not context.source_contracts_qualified:
        reasons.append("PROVIDER_SOURCE_CONTRACTS_UNQUALIFIED")
    if not context.no_independent_stop:
        reasons.append("INDEPENDENT_STOP")
    if approval is None:
        reasons.append("EXPLICIT_OWNER_APPROVAL_REQUIRED")
    else:
        if approval.review_sha256 != reset_review_digest(request, context, calendar):
            reasons.append("ACTION_BOUND_REVIEW_CHANGED")
        if (
            approval.credential_sha256 != context.designated_credential_sha256
            or not approval.external_signature_fixture_verified
        ):
            reasons.append("EXTERNAL_OWNER_APPROVAL_UNVERIFIED")
        approval_age = (now - approval.approved_at).total_seconds()
        if not 0 <= approval_age < 300 or approval.approved_at < context.reconciled_at:
            reasons.append("ORDERED_FRESH_OWNER_APPROVAL_REQUIRED")
        if str(approval.approval_id) in used_approval_ids:
            reasons.append("APPROVAL_REPLAY")
    return {
        "schema_version": "webull-synthetic-reset-review-v1",
        "synthetic_preconditions_passed": not reasons,
        "reason_codes": reasons,
        "production_owner_approval_verified": False,
        "approval_consumed": False,
        "controller_admitted": False,
        "reset_performed": False,
        "execution_available": False,
        "trial_started": False,
    }
