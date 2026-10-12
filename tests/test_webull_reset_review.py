from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from uuid import uuid4

import pytest
from pydantic import ValidationError

from market_data.nyse_calendar import NysePublishedCalendar
from security.webull_control_request import ControlRequest
from security.webull_reset_review import (
    SyntheticOwnerApproval,
    SyntheticResetContext,
    evaluate_synthetic_reset_review,
    reset_review_digest,
)

NOW = datetime(2026, 10, 5, 15, tzinfo=UTC)


def fixture(**changes):
    calendar = NysePublishedCalendar(Path("conf/nyse-calendar-2026.json"))
    request = ControlRequest(
        schema_version="webull-control-request-v1",
        action="REQUEST_RESET_REVIEW",
        account_binding_sha256="a" * 64,
        expected_state_sha256="b" * 64,
        request_id=str(uuid4()),
    )
    context = SyntheticResetContext(
        **(
            {
                "account_binding_sha256": "a" * 64,
                "state_sha256": "b" * 64,
                "policy_sha256": "c" * 64,
                "designated_credential_sha256": "d" * 64,
                "breach_new_york_day": date(2026, 10, 2),
                "latch_reasons": ("ACCOUNT_DAILY_LOSS",),
                "reconciled_at": NOW - timedelta(seconds=2),
                "reconciled_state_sha256": "b" * 64,
                "reconciliation_complete": True,
                "source_contracts_qualified": True,
                "calendar_source_qualified": True,
                "no_independent_stop": True,
            }
            | changes
        )
    )
    approval = SyntheticOwnerApproval(
        action="APPROVE_WEBULL_DAILY_LOSS_RESET",
        approval_id=uuid4(),
        review_sha256=reset_review_digest(request, context, calendar),
        credential_sha256="d" * 64,
        approved_at=NOW - timedelta(seconds=1),
        external_signature_fixture_verified=True,
    )
    return request, context, calendar, approval


def evaluate(parts, **changes):
    request, context, calendar, approval = parts
    return evaluate_synthetic_reset_review(
        request, context, **({"calendar": calendar, "now": NOW, "approval": approval} | changes)
    )


def test_complete_synthetic_review_never_consumes_approval_or_resets():
    result = evaluate(fixture())
    assert result["synthetic_preconditions_passed"]
    for name in [
        "production_owner_approval_verified",
        "approval_consumed",
        "controller_admitted",
        "reset_performed",
        "execution_available",
        "trial_started",
    ]:
        assert result[name] is False


@pytest.mark.parametrize(
    "changes,code",
    [
        ({"account_binding_sha256": "e" * 64}, "ACCOUNT_BINDING_CHANGED"),
        ({"state_sha256": "e" * 64}, "EXPECTED_STATE_CHANGED"),
        ({"latch_reasons": ("CUMULATIVE_LOSS",)}, "INDEPENDENT_LATCH_NOT_RESETTABLE"),
        ({"latch_reasons": ()}, "INDEPENDENT_LATCH_NOT_RESETTABLE"),
        ({"breach_new_york_day": date(2026, 10, 5)}, "NEXT_NYSE_DAY_UNQUALIFIED"),
        ({"calendar_source_qualified": False}, "NEXT_NYSE_DAY_UNQUALIFIED"),
        ({"reconciled_at": NOW - timedelta(seconds=61)}, "FRESH_RECONCILIATION_REQUIRED"),
        ({"reconciled_at": NOW + timedelta(seconds=1)}, "FRESH_RECONCILIATION_REQUIRED"),
        ({"reconciled_state_sha256": "e" * 64}, "FRESH_RECONCILIATION_REQUIRED"),
        ({"reconciliation_complete": False}, "FRESH_RECONCILIATION_REQUIRED"),
        ({"source_contracts_qualified": False}, "PROVIDER_SOURCE_CONTRACTS_UNQUALIFIED"),
        ({"no_independent_stop": False}, "INDEPENDENT_STOP"),
    ],
)
def test_unqualified_sources_and_independent_stops_block_signed_fixture(changes, code):
    result = evaluate(fixture(**changes))
    assert not result["synthetic_preconditions_passed"] and code in result["reason_codes"]


def test_review_signature_scope_changes_when_policy_state_calendar_or_request_changes():
    parts = fixture()
    request, context, calendar, _ = parts
    original = reset_review_digest(request, context, calendar)
    changed = context.model_copy(update={"policy_sha256": "e" * 64})
    assert reset_review_digest(request, changed, calendar) != original
    assert (
        "ACTION_BOUND_REVIEW_CHANGED"
        in evaluate((request, changed, calendar, parts[3]))["reason_codes"]
    )
    calendar.digest = "e" * 64
    assert reset_review_digest(request, context, calendar) != original
    changed_request = request.model_copy(update={"request_id": str(uuid4())})
    assert reset_review_digest(changed_request, context, calendar) != original


@pytest.mark.parametrize(
    "changes,code",
    [
        ({"approved_at": NOW - timedelta(seconds=300)}, "ORDERED_FRESH_OWNER_APPROVAL_REQUIRED"),
        ({"approved_at": NOW - timedelta(seconds=3)}, "ORDERED_FRESH_OWNER_APPROVAL_REQUIRED"),
        ({"approved_at": NOW + timedelta(seconds=1)}, "ORDERED_FRESH_OWNER_APPROVAL_REQUIRED"),
        ({"credential_sha256": "e" * 64}, "EXTERNAL_OWNER_APPROVAL_UNVERIFIED"),
        ({"external_signature_fixture_verified": False}, "EXTERNAL_OWNER_APPROVAL_UNVERIFIED"),
    ],
)
def test_approval_order_freshness_and_owner_binding(changes, code):
    request, context, calendar, approval = fixture()
    changed = SyntheticOwnerApproval.model_validate(approval.model_dump() | changes)
    assert code in evaluate((request, context, calendar, changed))["reason_codes"]


def test_missing_approval_and_replay_never_grant_or_consume_authority():
    parts = fixture()
    assert "EXPLICIT_OWNER_APPROVAL_REQUIRED" in evaluate(parts, approval=None)["reason_codes"]
    used = frozenset({str(parts[3].approval_id)})
    result = evaluate(parts, used_approval_ids=used)
    assert "APPROVAL_REPLAY" in result["reason_codes"] and not result["approval_consumed"]
    assert used == frozenset({str(parts[3].approval_id)})


def test_schedule_coverage_and_nontrading_day_fail_closed():
    assert (
        "NEXT_NYSE_DAY_UNQUALIFIED"
        in evaluate(fixture(), now=NOW - timedelta(days=1))["reason_codes"]
    )
    assert (
        "NEXT_NYSE_DAY_UNQUALIFIED"
        in evaluate(fixture(), now=datetime(2027, 1, 4, tzinfo=UTC))["reason_codes"]
    )


def test_synthetic_schema_cannot_claim_production_or_accept_naive_clock():
    _, context, _, approval = fixture()
    with pytest.raises(ValidationError):
        SyntheticResetContext.model_validate(
            context.model_dump() | {"evidence_class": "PRODUCTION"}
        )
    with pytest.raises(ValidationError):
        SyntheticOwnerApproval.model_validate(
            approval.model_dump() | {"external_signature_fixture_verified": 1}
        )
    with pytest.raises(ValueError, match="Aware"):
        evaluate(fixture(), now=datetime(2026, 10, 5))  # noqa: DTZ001 - intentional invalid clock
