from scripts.observe_paper_trial import run_cycles
from workers.paper_trial_observer import observe_once


def test_deadline_persists_and_restart_does_not_dispatch(tmp_path):
    from threading import Event

    from risk.paper_state import PaperState
    from scripts.observe_paper_trial import run_guarded_cycles

    path = tmp_path / "paper.sqlite"
    store = PaperState.initialize(path, account_binding="a" * 64)
    release = Event()
    calls = []

    def blocked():
        calls.append(1)
        release.wait(2)
        return {"blockers": [], "execution_available": False}

    try:
        reports = run_guarded_cycles(
            blocked, store, cycles=3, interval_seconds=5, deadline_seconds=0.02
        )
        assert len(reports) == 1 and calls == [1]
        assert "OBSERVER_DEADLINE_MISSED" in PaperState(path).read()["latch_reasons"]
        restarted = run_guarded_cycles(blocked, PaperState(path), cycles=3, interval_seconds=5)
        assert restarted[0]["blockers"] == ["SERVICE_RECOVERY_REQUIRED"]
        assert calls == [1]
    finally:
        release.set()


def test_cycle_deadline_is_blocked_and_count_is_bounded():
    moments = iter([0, 6, 10, 11])
    sleeps = []
    reports = run_cycles(
        lambda: {"blockers": [], "execution_available": False},
        cycles=2,
        interval_seconds=5,
        monotonic=lambda: next(moments),
        sleep=sleeps.append,
    )
    assert "OBSERVER_DEADLINE_MISSED" in reports[0]["blockers"]
    assert sleeps == [] and len(reports) == 1 and not reports[0]["execution_available"]


def test_failed_source_cycle_latches_without_secret_output():
    class Account:
        def observe(self):
            raise RuntimeError("private-secret")

    class Store:
        def __init__(self):
            self.reasons = []

        def latch(self, reason):
            self.reasons.append(reason)

    class Ledger:
        store = Store()

    ledger = Ledger()
    report = observe_once(
        account_reader=Account(),
        activity_reader=None,
        quote_reader=None,
        calendar=None,
        ledger=ledger,
        clock_check=None,
        now=None,
    )
    assert ledger.store.reasons == ["INTEGRATED_OBSERVER_FAILED", "ACCOUNT_READ_FAILED"]
    assert "private-secret" not in str(report) and not report["execution_available"]


def test_active_scope_interval_above_five_seconds_blocks():
    report = run_cycles(
        lambda: {"active_scope": True, "blockers": [], "execution_available": False},
        cycles=1,
        interval_seconds=60,
    )[0]
    assert "ACTIVE_SCOPE_TIMER_TOO_SLOW" in report["blockers"]


def test_quote_failure_does_not_skip_daily_loss_check(monkeypatch):
    from types import SimpleNamespace

    import workers.paper_trial_observer as worker
    from tests.test_paper_control_pipeline import NOW

    latches = []
    store = SimpleNamespace(read=lambda: {"binding": "a" * 64}, latch=latches.append)
    ledger = SimpleNamespace(
        store=store,
        read=lambda: {"acquisition_cutoff": NOW.isoformat()},
        import_batch=lambda *a, **kw: None,
    )
    account = SimpleNamespace(account_binding_sha256="a" * 64)
    reader = SimpleNamespace(observe=lambda: account)
    monkeypatch.setattr(worker, "reconcile_cash", lambda *a, **kw: {})
    monkeypatch.setattr(worker, "simulated_settlement", lambda *a, **kw: {})
    checked = []

    def daily(*args, **kwargs):
        checked.append(True)
        return {"daily_loss_breach": True, "blockers": ["ACCOUNT_DAILY_LOSS"]}

    class Quote:
        def read(self, symbol):
            assert checked == [True]
            raise RuntimeError("private-provider-error")

    monkeypatch.setattr(worker, "evaluate_daily_loss", daily)
    result = worker.observe_once(
        account_reader=reader,
        activity_reader=SimpleNamespace(read=lambda **kw: None),
        quote_reader=Quote(),
        calendar=None,
        ledger=ledger,
        clock_check=dict,
        now=lambda: NOW,
    )
    assert result["daily_loss"]["daily_loss_breach"]
    assert "QUOTE_READ_FAILED" in result["blockers"]
    assert "private-provider-error" not in str(result)
