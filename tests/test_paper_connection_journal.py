import pytest

from risk.paper_state import PaperState, PaperStateError
from scripts.check_alpaca_trade_updates import probe
from tests.test_paper_trade_update_probe import AUTH, LISTEN, Stream
from workers.paper_connection_journal import PaperConnectionJournal


def test_connection_checkpoint_precedes_all_broker_event_callbacks():
    stream = Stream([AUTH, LISTEN, {"stream": "trade_updates", "data": {"event": "fill"}}])
    ticks = iter(range(100))
    calls = []
    result = probe(
        "fixture",
        "fixture",
        connector=lambda *a, **kw: stream,
        monotonic=lambda: next(ticks),
        on_connected=lambda: calls.append("CHECK"),
        on_event=lambda row: calls.append("EVENT"),
    )
    assert result["monitor_completed"] and calls == ["CHECK", "EVENT"]


def test_failed_checkpoint_never_processes_events():
    stream = Stream([AUTH, LISTEN, {"stream": "trade_updates", "data": {"event": "fill"}}])

    def fail():
        raise RuntimeError("private-source-failure")

    result = probe(
        "fixture",
        "fixture",
        connector=lambda *a, **kw: stream,
        on_connected=fail,
        on_event=lambda row: pytest.fail("No event dispatch"),
    )
    assert not result["monitor_completed"] and "private" not in str(result)


def test_interrupted_connection_blocks_restart_and_preserves_latch(tmp_path):
    store = PaperState.initialize(tmp_path / "state.sqlite", account_binding="a" * 64)
    epoch = PaperConnectionJournal(store)
    epoch.connected_after_check(
        {"account_observed": True, "execution_available": False, "trial_started": False}
    )
    epoch.finish(completed=False)
    with pytest.raises(PaperStateError):
        PaperConnectionJournal(PaperState(store.path))
    assert store.read()["latched"] and not store.read()["execution_available"]


def test_normal_bounded_reconnect_still_requires_new_checkpoint(tmp_path):
    store = PaperState.initialize(tmp_path / "state.sqlite", account_binding="a" * 64)
    first = PaperConnectionJournal(store)
    with pytest.raises(PaperStateError):
        first.finish(completed=True)
    first.connected_after_check(
        {"account_observed": True, "execution_available": False, "trial_started": False}
    )
    first.finish(completed=True)
    second = PaperConnectionJournal(PaperState(store.path))
    assert second.identifier != first.identifier
    with pytest.raises(PaperStateError):
        second.finish(completed=True)
