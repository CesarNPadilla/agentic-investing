from datetime import UTC, date, datetime, timedelta

import pytest
from pydantic import ValidationError

from risk.evidence_v11 import SyntheticEvidence, SyntheticReviewBinding, check_synthetic_evidence

NOW = datetime(2026, 10, 1, 15, tzinfo=UTC)
PROPOSAL = "a"*64


def bundle(**changes):
    return SyntheticEvidence(**({"symbol": "AAPL", "quote_source": "synthetic-quote",
        "quote_symbol": "AAPL", "quote_status": "ACTIVE", "bid": "99", "ask": "100",
        "quote_event_time": NOW, "quote_received_time": NOW,
        "snapshot_source": "synthetic-ledger", "snapshot_digest": "b"*64,
        "snapshot_cutoff": NOW, "snapshot_complete": True, "snapshot_reconciled": True,
        "policy_digest": "c"*64, "calendar_source": "synthetic-calendar", "calendar_version": "fixture-v1",
        "session_date": date(2026, 10, 1), "session_open": NOW.replace(hour=13, minute=30),
        "session_close": NOW.replace(hour=20), "calendar_verified": True,
        "broker_regular_session_supported": True, "clock_synchronized": True} | changes))


def review(b, at=NOW):
    return SyntheticReviewBinding(evidence_digest=b.digest(), proposal_digest=PROPOSAL,
                                  risk_evaluated_at=at)


def check(b, at=NOW, binding=None):
    return check_synthetic_evidence(b, now=at, proposal_digest=PROPOSAL, review=binding or review(b))


def test_pass_is_synthetic_and_never_human_or_execution_authority():
    result = check(bundle())
    assert result.checks_passed
    assert not result.production_trusted and not result.human_approval_verified and not result.execution_available


@pytest.mark.parametrize("changes,code", [
    ({"clock_synchronized": False}, "CLOCK_UNVERIFIED"),
    ({"quote_symbol": "MSFT"}, "QUOTE_SYMBOL_MISMATCH"),
    ({"quote_status": "HALTED"}, "QUOTE_STATUS"),
    ({"bid": None}, "QUOTE_BID_ASK"), ({"bid": "101"}, "QUOTE_BID_ASK"),
    ({"quote_event_time": NOW-timedelta(seconds=31)}, "QUOTE_TIME"),
    ({"quote_received_time": NOW-timedelta(seconds=1)}, "QUOTE_TIME"),
    ({"quote_received_time": NOW+timedelta(seconds=1)}, "QUOTE_TIME"),
    ({"quote_event_time": None}, "QUOTE_TIME"),
    ({"snapshot_cutoff": NOW-timedelta(seconds=61)}, "SNAPSHOT_TIME"),
    ({"snapshot_cutoff": NOW+timedelta(seconds=1)}, "SNAPSHOT_TIME"),
    ({"snapshot_complete": False}, "SNAPSHOT_INCOMPLETE"),
    ({"snapshot_reconciled": False}, "SNAPSHOT_INCOMPLETE"),
    ({"calendar_verified": False}, "SESSION_UNVERIFIED"),
    ({"broker_regular_session_supported": False}, "SESSION_UNVERIFIED"),
    ({"session_open": None, "session_close": None}, "OUTSIDE_REGULAR_SESSION"),
])
def test_fail_closed_inputs(changes, code):
    assert code in check(bundle(**changes)).reason_codes


def test_exact_freshness_boundaries():
    assert check(bundle(quote_event_time=NOW-timedelta(seconds=30),
                        snapshot_cutoff=NOW-timedelta(seconds=60))).checks_passed


@pytest.mark.parametrize("field,value", [("policy_digest", "d"*64), ("snapshot_digest", "d"*64),
    ("ask", "101"), ("calendar_version", "changed"), ("quote_source", "changed")])
def test_changed_evidence_invalidates_binding(field, value):
    old = bundle(); changed = bundle(**{field: value})
    assert "REVIEW_BINDING_CHANGED" in check(changed, binding=review(old)).reason_codes


@pytest.mark.parametrize("seconds", [-1, 300])
def test_review_future_or_expired(seconds):
    b = bundle()
    assert "REVIEW_EXPIRED" in check(b, binding=review(b, NOW-timedelta(seconds=seconds))).reason_codes


def test_review_just_before_expiry_and_missing_review():
    b = bundle()
    assert check(b, binding=review(b, NOW-timedelta(seconds=299))).checks_passed
    assert "REVIEW_MISSING" in check_synthetic_evidence(b, now=NOW, proposal_digest=PROPOSAL).reason_codes


def test_early_close_excludes_exact_close_and_extended_hours():
    b = bundle(session_close=NOW.replace(hour=17))
    assert "OUTSIDE_REGULAR_SESSION" in check(b, at=NOW.replace(hour=17)).reason_codes
    assert "OUTSIDE_REGULAR_SESSION" in check(b, at=NOW.replace(hour=13)).reason_codes


@pytest.mark.parametrize("changes", [{"session_open": NOW}, {"session_close": NOW.replace(hour=21)},
    {"quote_event_time": NOW.replace(tzinfo=None)}, {"bid": "NaN"}, {"evidence_class": "LIVE"}])
def test_invalid_fixture_structure(changes):
    with pytest.raises(ValidationError):
        bundle(**changes)
