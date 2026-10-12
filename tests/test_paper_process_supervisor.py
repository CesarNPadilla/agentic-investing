import json
import sqlite3
import subprocess
import sys
import time

from risk.paper_state import PaperState
from workers.paper_process_supervisor import run_readonly_cycle, run_supervised_batch


def setup(tmp_path):
    root = tmp_path / "repository"
    root.mkdir()
    store = PaperState.initialize(tmp_path / "private.sqlite", account_binding="a" * 64)
    return root, store


def test_real_hung_readonly_child_is_killed_and_restart_refused(tmp_path):
    root, store = setup(tmp_path)
    children = []

    def factory(command, **kwargs):
        assert command[1:3] == ["-m", "scripts.observe_paper_trial"]
        child = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(30)"], **kwargs)
        children.append(child)
        return child

    result = run_readonly_cycle(
        root,
        env_file=tmp_path / "external.env",
        ledger_file=store.path,
        timeout_seconds=0.05,
        process_factory=factory,
    )
    assert result["child_terminated"] and children[0].poll() is not None
    assert "READONLY_PROCESS_DEADLINE_MISSED" in store.read()["latch_reasons"]
    restart = run_readonly_cycle(
        root, env_file=tmp_path / "external.env", ledger_file=store.path, process_factory=factory
    )
    assert restart["blockers"] == ["READONLY_PROCESS_RECOVERY_REQUIRED"]
    assert len(children) == 1


def test_child_report_preserves_blockers_without_enabling_execution(tmp_path):
    root, store = setup(tmp_path)
    payload = json.dumps(
        [
            {
                "account_observed": True,
                "blockers": ["STATUS_UNVERIFIED"],
                "execution_available": False,
                "trial_started": False,
            }
        ]
    )

    def factory(command, **kwargs):
        return subprocess.Popen([sys.executable, "-c", f"print({payload!r})"], **kwargs)

    result = run_readonly_cycle(
        root, env_file=tmp_path / "external.env", ledger_file=store.path, process_factory=factory
    )
    assert result["blockers"] == ["STATUS_UNVERIFIED"] and not result["execution_available"]


def test_private_child_error_is_sanitized(tmp_path):
    root, store = setup(tmp_path)

    def factory(command, **kwargs):
        return subprocess.Popen(
            [sys.executable, "-c", "print('private-provider-detail')"], **kwargs
        )

    result = run_readonly_cycle(
        root, env_file=tmp_path / "external.env", ledger_file=store.path, process_factory=factory
    )
    assert result["blockers"] == ["READONLY_PROCESS_FAILED"]
    assert "private-provider-detail" not in str(result)


def test_abandoned_batch_refuses_restart(tmp_path):
    root, store = setup(tmp_path)
    with store.transaction() as state:
        state["paper_supervisor_sessions"] = {"crashed": {"completed": False}}
    result = run_supervised_batch(
        root,
        env_file=tmp_path / "external.env",
        ledger_file=store.path,
        cycle_runner=lambda *a, **kw: None,
    )
    assert result["blockers"] == ["READONLY_SUPERVISOR_RECOVERY_REQUIRED"]


def test_batch_failure_is_not_marked_complete(tmp_path):
    root, store = setup(tmp_path)
    result = run_supervised_batch(
        root,
        env_file=tmp_path / "external.env",
        ledger_file=store.path,
        cycle_runner=lambda *a, **kw: {
            "blockers": ["READONLY_PROCESS_FAILED"],
            "execution_available": False,
        },
    )
    assert not result["batch_completed"]
    assert not next(iter(store.read()["paper_supervisor_sessions"].values()))["completed"]


def test_timeout_releases_child_sqlite_lock_and_rolls_back(tmp_path):
    root, store = setup(tmp_path)
    ready = tmp_path / "ready"

    def factory(command, **kwargs):
        code = (
            "import sqlite3,time; from pathlib import Path; "
            f"db=sqlite3.connect({str(store.path)!r}); "
            "db.execute('BEGIN IMMEDIATE'); "
            "db.execute('CREATE TABLE unfinished_fixture (value INTEGER)'); "
            f"Path({str(ready)!r}).write_text('ready'); time.sleep(30)"
        )
        child = subprocess.Popen([sys.executable, "-c", code], **kwargs)
        deadline = time.monotonic() + 2
        while not ready.exists() and time.monotonic() < deadline:
            time.sleep(0.005)
        if not ready.exists():
            child.kill()
            child.communicate(timeout=2)
            raise AssertionError("Fixture did not acquire SQLite lock")
        return child

    result = run_readonly_cycle(
        root,
        env_file=tmp_path / "external.env",
        ledger_file=store.path,
        timeout_seconds=0.05,
        process_factory=factory,
    )
    assert result["child_terminated"]
    with sqlite3.connect(store.path) as db:
        assert (
            db.execute("SELECT name FROM sqlite_master WHERE name='unfinished_fixture'").fetchone()
            is None
        )
    assert "READONLY_PROCESS_DEADLINE_MISSED" in store.read()["latch_reasons"]
