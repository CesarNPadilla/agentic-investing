import json
import subprocess
import sys

from risk.paper_state import PaperState
from workers.paper_event_process_supervisor import supervise_events


def setup(tmp_path):
    root = tmp_path / "repository"
    root.mkdir()
    store = PaperState.initialize(tmp_path / "private.sqlite", account_binding="a" * 64)
    return root, store


def run(root, store, factory, **options):
    return supervise_events(
        root,
        env_file=store.path.parent / "paper.env",
        ledger_file=store.path,
        owner_credential_file=store.path.parent / "owner.json",
        process_factory=factory,
        **options,
    )


def child_factory(code, children):
    def factory(command, **kwargs):
        assert command[1:3] == ["-m", "scripts.observe_paper_events"]
        assert "--heartbeat-lines" in command
        child = subprocess.Popen([sys.executable, "-u", "-c", code], **kwargs)
        children.append(child)
        return child

    return factory


def test_hung_actual_child_is_killed_and_no_automatic_restart(tmp_path):
    root, store = setup(tmp_path)
    children = []
    factory = child_factory("import time;time.sleep(30)", children)
    result = run(root, store, factory, timeout_seconds=0.1)
    assert not result["monitor_completed"] and result["child_terminated"]
    assert children[0].poll() is not None
    assert run(root, store, factory)["blockers"] == ["EVENT_PROCESS_RECOVERY_REQUIRED"]
    assert len(children) == 1


def test_completed_checks_preserve_blockers_and_require_clean_exit(tmp_path):
    root, store = setup(tmp_path)
    rows = [
        {
            "kind": "check",
            "sequence": 1,
            "account_observed": True,
            "blockers": ["STATUS_BOOTSTRAP_UNQUALIFIED"],
            "execution_available": False,
            "trial_started": False,
        },
        {
            "kind": "complete",
            "diagnostic_cycles": 1,
            "stream": {"monitor_completed": True},
            "latest_diagnostic": {
                "execution_available": False,
                "trial_started": False,
                "account_observed": True,
            },
            "execution_available": False,
            "trial_started": False,
        },
    ]
    code = "\n".join(f"print({json.dumps(row)!r},flush=True)" for row in rows)
    result = run(root, store, child_factory(code, []))
    assert result["monitor_completed"] and result["checks_completed"] == 1
    assert result["blockers"] == ["STATUS_BOOTSTRAP_UNQUALIFIED"]
    assert not result["execution_available"]
    assert all(row["completed"] for row in store.read()["paper_event_process_sessions"].values())


def test_malformed_or_execution_enabled_output_never_succeeds(tmp_path):
    root, store = setup(tmp_path)
    result = run(
        root, store, child_factory("print('private-invalid-provider-response',flush=True)", [])
    )
    assert not result["monitor_completed"] and "private" not in str(result)
    assert "EVENT_PROCESS_WATCHDOG_FAILED" in store.read()["latch_reasons"]


def test_out_of_order_sequence_and_late_completion_block(tmp_path):
    root, store = setup(tmp_path)
    row = {
        "kind": "check",
        "sequence": 2,
        "account_observed": True,
        "blockers": [],
        "execution_available": False,
        "trial_started": False,
    }
    result = run(root, store, child_factory(f"print({json.dumps(row)!r},flush=True)", []))
    assert not result["monitor_completed"]


def test_abandoned_parent_session_requires_recovery_without_child(tmp_path):
    root, store = setup(tmp_path)
    with store.transaction() as state:
        state["paper_event_process_sessions"] = {"abandoned": {"completed": False}}
    result = run(root, store, lambda *a, **kw: (_ for _ in ()).throw(AssertionError("No child")))
    assert result["blockers"] == ["EVENT_PROCESS_RECOVERY_REQUIRED"]
