from threading import Event
from uuid import uuid4

import pytest

from risk.paper_state import PaperState, PaperStateError
from workers.paper_event_observer import PaperEventObserver


def store(tmp_path):
    return PaperState.initialize(tmp_path / "paper.sqlite", account_binding="a" * 64)


def test_every_event_and_timer_is_journaled_before_diagnostic(tmp_path):
    state = store(tmp_path)
    calls = []

    def cycle():
        records = state.read()["paper_event_checks"]
        assert any(not row["completed"] for row in records.values())
        calls.append(True)
        return {
            "account_observed": True,
            "blockers": ["MARKET_STATUS_UNVERIFIED"],
            "execution_available": False,
        }

    observer = PaperEventObserver(state, cycle, account_binding="a" * 64)
    payload = {"event": "partial_fill", "order": {"id": str(uuid4()), "symbol": "INTC"}}
    observer.on_event(payload)
    observer.on_event(payload)  # Replay still causes a check, not a second cash booking.
    observer.on_timer()
    assert len(calls) == 3
    records = state.read()["paper_event_checks"].values()
    assert sorted(row["trigger"] for row in records) == ["FILL", "FILL", "TIMER"]
    assert all(row["completed"] for row in records)
    assert not state.read()["execution_available"]


def test_deadline_stops_events_and_survives_restart(tmp_path):
    state, release = store(tmp_path), Event()
    observer = PaperEventObserver(
        state, lambda: release.wait(2), account_binding="a" * 64, timeout_seconds=0.02
    )
    try:
        with pytest.raises(PaperStateError):
            observer.on_timer()
        assert observer.stopped
        with pytest.raises(PaperStateError):
            observer.on_timer()
        with pytest.raises(PaperStateError):
            PaperEventObserver(PaperState(state.path), lambda: None, account_binding="a" * 64)
    finally:
        release.set()


def test_unknown_and_foreign_events_latch_without_running_cycle(tmp_path):
    state = store(tmp_path)
    observer = PaperEventObserver(
        state, lambda: pytest.fail("must not dispatch"), account_binding="a" * 64
    )
    with pytest.raises(PaperStateError):
        observer.on_event({"event": "fill", "order": {"id": str(uuid4()), "symbol": "OTHER"}})
    assert "PAPER_EVENT_UNQUALIFIED" in state.read()["latch_reasons"]


def test_active_scope_gap_stops_before_another_read(tmp_path):
    state = store(tmp_path)
    calls = []
    ticks = iter([10, 16])

    def cycle():
        calls.append(True)
        return {
            "account_observed": True,
            "active_scope": True,
            "blockers": [],
            "execution_available": False,
        }

    observer = PaperEventObserver(
        state, cycle, account_binding="a" * 64, monotonic=lambda: next(ticks)
    )
    observer.on_timer()
    with pytest.raises(PaperStateError):
        observer.on_timer()
    assert calls == [True] and observer.stopped
    assert "ACTIVE_SCOPE_MONITORING_DEADLINE_MISSED" in state.read()["latch_reasons"]
    with pytest.raises(PaperStateError):
        PaperEventObserver(PaperState(state.path), cycle, account_binding="a" * 64)


def test_crash_after_journal_claim_blocks_restart_without_dispatch(tmp_path):
    state = store(tmp_path)
    with state.transaction() as value:
        value["paper_event_checks"] = {"abandoned": {"completed": False}}
    with pytest.raises(PaperStateError):
        PaperEventObserver(
            PaperState(state.path), lambda: pytest.fail("no dispatch"), account_binding="a" * 64
        )


def test_failed_source_is_not_recorded_as_completed(tmp_path):
    state = store(tmp_path)
    observer = PaperEventObserver(
        state,
        lambda: {"blockers": ["INTEGRATED_OBSERVER_FAILED"], "execution_available": False},
        account_binding="a" * 64,
    )
    with pytest.raises(PaperStateError):
        observer.on_timer()
    assert not next(iter(state.read()["paper_event_checks"].values()))["completed"]
    with pytest.raises(PaperStateError):
        PaperEventObserver(PaperState(state.path), lambda: None, account_binding="a" * 64)
