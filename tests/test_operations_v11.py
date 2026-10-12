from datetime import UTC, date, datetime, timedelta

import pytest
from pydantic import ValidationError

from risk.operations_v11 import (
    MonitoringInput,
    SyntheticDailyResetEvidence,
    check_synthetic_daily_reset,
    monitoring_deadline,
)

NOW = datetime(2026, 10, 5, 15, tzinfo=UTC)


def reset(**changes):
    return SyntheticDailyResetEvidence(**({"latch_reasons": ("ACCOUNT_DAILY_LOSS",),
        "breach_new_york_day": date(2026,10,2), "next_trading_day": date(2026,10,5),
        "calendar_verified": True, "designated_owner_id": "fixture-human", "approving_human_id": "fixture-human",
        "authentication_source": "EXTERNAL_SYNTHETIC_VERIFIER", "authentication_verified": True,
        "reconciled_at": NOW-timedelta(seconds=1), "reconciliation_complete": True,
        "no_independent_hard_stop": True, "approved_at": NOW, "explicit_human_approval": True,
        "approval_nonce": "fixture-once", "nonce_unused": True} | changes))


def test_ordered_weekend_reset_preconditions_never_perform_reset():
    result = check_synthetic_daily_reset(reset(), now=NOW)
    assert result.synthetic_reset_preconditions_passed
    assert not result.reset_performed and not result.execution_available
    assert not result.human_authentication_production_verified


@pytest.mark.parametrize("changes,code", [
    ({"latch_reasons": ("CUMULATIVE_LOSS",)}, "INDEPENDENT_LATCH_NOT_RESETTABLE"),
    ({"latch_reasons": ()}, "INDEPENDENT_LATCH_NOT_RESETTABLE"),
    ({"calendar_verified": False}, "NEXT_TRADING_DAY_UNVERIFIED"),
    ({"next_trading_day": date(2026,10,6)}, "NEXT_TRADING_DAY_UNVERIFIED"),
    ({"reconciled_at": NOW-timedelta(seconds=61)}, "FRESH_RECONCILIATION_REQUIRED"),
    ({"reconciliation_complete": False}, "FRESH_RECONCILIATION_REQUIRED"),
    ({"approved_at": NOW-timedelta(seconds=2)}, "ORDERED_HUMAN_APPROVAL_REQUIRED"),
    ({"explicit_human_approval": False}, "ORDERED_HUMAN_APPROVAL_REQUIRED"),
    ({"authentication_source": "AGENT_RUNTIME"}, "EXTERNAL_OWNER_AUTHENTICATION_REQUIRED"),
    ({"approving_human_id": "fixture-other"}, "EXTERNAL_OWNER_AUTHENTICATION_REQUIRED"),
    ({"authentication_verified": False}, "EXTERNAL_OWNER_AUTHENTICATION_REQUIRED"),
    ({"nonce_unused": False}, "APPROVAL_REPLAY"),
    ({"no_independent_hard_stop": False}, "INDEPENDENT_HARD_STOP"),
])
def test_reset_blockers(changes, code):
    assert code in check_synthetic_daily_reset(reset(**changes), now=NOW).reason_codes


@pytest.mark.parametrize("event", ["FILL", "ORDER"])
def test_event_checks_run_even_when_idle(event):
    result = monitoring_deadline(MonitoringInput(now_monotonic=10, last_completed_check_monotonic=10,
                                                open_orders=0, open_positions=0, event=event))
    assert result.check_due and not result.fail_closed_required


@pytest.mark.parametrize("interval", [1,2,3,4,5])
def test_timer_range_exact_deadline_then_overdue(interval):
    data = {"now_monotonic": interval, "last_completed_check_monotonic": 0, "open_orders": 1, "open_positions": 0, "timer_seconds": interval}
    assert monitoring_deadline(MonitoringInput(**data)).check_due
    assert not monitoring_deadline(MonitoringInput(**data)).fail_closed_required
    data["now_monotonic"] = interval+0.01
    assert monitoring_deadline(MonitoringInput(**data)).fail_closed_required


def test_missing_check_and_clock_regression_block():
    assert monitoring_deadline(MonitoringInput(now_monotonic=0, open_orders=0, open_positions=1)).fail_closed_required
    assert monitoring_deadline(MonitoringInput(now_monotonic=1, last_completed_check_monotonic=2, open_orders=0, open_positions=0)).fail_closed_required


@pytest.mark.parametrize("interval", [0,6,1.5,True])
def test_invalid_cadence_rejected(interval):
    with pytest.raises(ValidationError):
        MonitoringInput(timer_seconds=interval, now_monotonic=0, open_orders=0, open_positions=0)
