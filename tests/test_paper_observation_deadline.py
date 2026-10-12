from threading import Event

from workers.paper_observation_deadline import bounded_observation


def test_blocked_reader_latches_without_waiting_for_read_completion():
    release, finished = Event(), Event()
    latches = []

    def read():
        release.wait(2)
        finished.set()
        return {"stale": True}

    try:
        report = bounded_observation(read, timeout_seconds=0.02, on_timeout=latches.append)
        assert latches == ["OBSERVER_DEADLINE_MISSED"]
        assert not finished.is_set()
        assert "stale" not in report
        release.set()
        assert finished.wait(1)
        assert "stale" not in report
        assert not report["execution_available"]
    finally:
        release.set()


def test_timely_result_is_returned():
    assert bounded_observation(
        lambda: {"ok": True}, timeout_seconds=1, on_timeout=lambda _: None
    ) == {"ok": True}


def test_latch_failure_remains_blocked():
    release = Event()

    def fail(_):
        raise RuntimeError("private-store-detail")

    try:
        result = bounded_observation(lambda: release.wait(2), timeout_seconds=0.02, on_timeout=fail)
        assert "OBSERVER_PERSISTENCE_FAILED" in result["blockers"]
        assert "private-store-detail" not in str(result)
    finally:
        release.set()
