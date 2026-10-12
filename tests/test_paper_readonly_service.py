import pytest

from risk.paper_state import PaperState
from workers.paper_readonly_service import run_service


def store(tmp_path):
    return PaperState.initialize(tmp_path / "state.sqlite", account_binding="a" * 64)


def good_report():
    return {
        "monitor_completed": True,
        "checks_completed": 4,
        "latest_diagnostic": {
            "active_scope": False,
            "account_observed": True,
            "execution_available": False,
            "trial_started": False,
        },
        "blockers": ["STATUS_BOOTSTRAP_UNQUALIFIED"],
        "execution_available": False,
        "trial_started": False,
    }


def test_completed_windows_report_blockers_and_keep_latch(tmp_path):
    state, rows = store(tmp_path), []
    result = run_service(
        state,
        good_report,
        regular_session=lambda: True,
        stop_requested=lambda: False,
        max_windows=2,
        report_sink=rows.append,
    )
    assert result["status"] == "COMPLETE" and result["windows_completed"] == 2
    assert all(row["blockers"] == ["STATUS_BOOTSTRAP_UNQUALIFIED"] for row in rows)
    assert state.read()["latched"] and not state.read()["execution_available"]


@pytest.mark.parametrize("mode", ["STOP", "CLOSED"])
def test_stop_and_session_close_do_not_contact_broker(tmp_path, mode):
    result = run_service(
        store(tmp_path),
        lambda: pytest.fail("No broker access"),
        regular_session=lambda: mode != "CLOSED",
        stop_requested=lambda: mode == "STOP",
    )
    assert result["windows_completed"] == 0


def test_failure_is_sanitized_and_does_not_restart(tmp_path):
    state = store(tmp_path)

    def failure():
        raise RuntimeError("private-source-value")

    result = run_service(state, failure, regular_session=lambda: True, stop_requested=lambda: False)
    assert result["status"] == "FAILED" and "private" not in str(result)
    second = run_service(
        state,
        lambda: pytest.fail("No restart"),
        regular_session=lambda: True,
        stop_requested=lambda: False,
    )
    assert second["status"] == "RECOVERY_REQUIRED"


def test_active_exposure_blocks(tmp_path):
    state = store(tmp_path)
    report = good_report()
    report["latest_diagnostic"]["active_scope"] = True
    assert (
        run_service(
            state, lambda: report, regular_session=lambda: True, stop_requested=lambda: False
        )["status"]
        == "FAILED"
    )


def test_stop_during_run_preserves_completed_count(tmp_path):
    state = store(tmp_path)
    calls = []
    result = run_service(
        state,
        good_report,
        regular_session=lambda: True,
        stop_requested=lambda: len(calls) == 1,
        report_sink=lambda row: calls.append(row),
    )
    assert result["status"] == "STOPPED" and result["windows_completed"] == 1


def test_abandoned_service_blocks_source_access(tmp_path):
    state = store(tmp_path)
    with state.transaction() as data:
        data["paper_readonly_service_sessions"] = {"old": {"status": "RUNNING"}}
    result = run_service(
        state,
        lambda: pytest.fail("No source access"),
        regular_session=lambda: True,
        stop_requested=lambda: False,
    )
    assert result["status"] == "RECOVERY_REQUIRED"


@pytest.mark.parametrize("field,value", [("execution_available", True), ("trial_started", True)])
def test_diagnostic_activation_is_rejected(tmp_path, field, value):
    report = good_report()
    report["latest_diagnostic"][field] = value
    result = run_service(
        store(tmp_path), lambda: report, regular_session=lambda: True, stop_requested=lambda: False
    )
    assert result["status"] == "FAILED"
