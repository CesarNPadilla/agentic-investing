from datetime import UTC, datetime, timedelta

import pytest

from market_data.paper_status import PaperStatusState, apply_status, disconnect, status_reasons

NOW = datetime(2026, 10, 5, 15, tzinfo=UTC)


def event(code, tape="C", when=NOW):
    return {"T": "s", "S": "INTC", "sc": code, "z": tape, "t": when.isoformat()}


@pytest.mark.parametrize(
    "code,tape,status",
    [
        ("H", "C", "HALTED"),
        ("P", "C", "HALTED"),
        ("Q", "C", "UNKNOWN"),
        ("T", "C", "RESUME_OBSERVED"),
        ("2", "A", "HALTED"),
        ("F", "B", "HALTED"),
        ("3", "A", "RESUME_OBSERVED"),
        ("T", "A", "UNKNOWN"),
    ],
)
def test_tape_specific_codes_cannot_grant_execution(code, tape, status):
    state = apply_status(
        PaperStatusState(symbol="INTC", connection_epoch="one"),
        event(code, tape),
        connection_epoch="one",
        received_at=NOW,
    )
    assert state.observed_status == status and not state.execution_available
    assert "STATUS_SOURCE_BOOTSTRAP_UNQUALIFIED" in status_reasons(state, now=NOW)


def test_disconnect_old_epoch_and_out_of_order_messages_block():
    s = PaperStatusState(symbol="INTC", connection_epoch="one")
    s = apply_status(s, event("T"), connection_epoch="one", received_at=NOW)
    older = apply_status(
        s, event("H", when=NOW - timedelta(seconds=1)), connection_epoch="one", received_at=NOW
    )
    assert older.continuity_lost and older.observed_status == "UNKNOWN"
    reconnected = disconnect(s, new_epoch="two")
    assert "STATUS_CONTINUITY_LOST" in status_reasons(reconnected, now=NOW)
    with pytest.raises(ValueError):
        apply_status(reconnected, event("T"), connection_epoch="one", received_at=NOW)


def test_same_time_conflict_exact_replay_future_and_wrong_symbol():
    s = apply_status(
        PaperStatusState(symbol="INTC", connection_epoch="one"),
        event("T"),
        connection_epoch="one",
        received_at=NOW,
    )
    assert (
        apply_status(s, event("T"), connection_epoch="one", received_at=NOW + timedelta(seconds=5))
        == s
    )
    assert apply_status(s, event("H"), connection_epoch="one", received_at=NOW).continuity_lost
    with pytest.raises(ValueError):
        apply_status(
            s, event("T", when=NOW + timedelta(seconds=1)), connection_epoch="one", received_at=NOW
        )
    wrong = event("T")
    wrong["S"] = "AAPL"
    with pytest.raises(ValueError):
        apply_status(s, wrong, connection_epoch="one", received_at=NOW)
