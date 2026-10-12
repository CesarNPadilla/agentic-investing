"""Durable empty-account diagnostic service; never a trading trial runner."""

import re
from datetime import UTC, datetime
from uuid import uuid4


def run_service(
    store,
    run_window,
    *,
    regular_session,
    stop_requested,
    max_windows=390,
    report_sink=lambda row: None,
):
    if type(max_windows) is not int or not 1 <= max_windows <= 390:
        raise ValueError("Bounded diagnostic service required")
    if stop_requested():
        return {
            "status": "STOP_REQUESTED",
            "windows_completed": 0,
            "execution_available": False,
            "trial_started": False,
        }
    identifier = str(uuid4())
    with store.transaction() as state:
        sessions = state.setdefault("paper_readonly_service_sessions", {})
        if any(
            row.get("status") not in {"COMPLETE", "STOPPED", "SESSION_CLOSED"}
            for row in sessions.values()
        ):
            return {
                "status": "RECOVERY_REQUIRED",
                "windows_completed": 0,
                "execution_available": False,
                "trial_started": False,
            }
        sessions[identifier] = {
            "started_at_utc": datetime.now(UTC).isoformat(),
            "status": "RUNNING",
            "windows_completed": 0,
        }
    completed = 0
    status = "COMPLETE"
    try:
        for _ in range(max_windows):
            if stop_requested():
                status = "STOPPED"
                break
            if not regular_session():
                status = "SESSION_CLOSED"
                break
            report = run_window()
            diagnostic = report.get("latest_diagnostic", {})
            if (
                report.get("monitor_completed") is not True
                or report.get("execution_available") is not False
                or report.get("trial_started") is not False
                or diagnostic.get("active_scope") is not False
                or diagnostic.get("account_observed") is not True
                or diagnostic.get("execution_available") is not False
                or diagnostic.get("trial_started") is not False
                or type(report.get("checks_completed")) is not int
                or report["checks_completed"] < 1
                or not isinstance(report.get("blockers"), list)
                or any(
                    not isinstance(reason, str) or not re.fullmatch(r"[A-Z0-9_]{1,100}", reason)
                    for reason in report["blockers"]
                )
            ):
                raise ValueError("Diagnostic-only service source or exposure unqualified")
            completed += 1
            summary = {
                "observed_at_utc": datetime.now(UTC).isoformat(),
                "windows_completed": completed,
                "checks_completed": report["checks_completed"],
                "blockers": report["blockers"],
                "execution_available": False,
                "trial_started": False,
            }
            report_sink(summary)
            with store.transaction() as state:
                state["paper_readonly_service_sessions"][identifier]["windows_completed"] = (
                    completed
                )
    except (RuntimeError, ValueError, TypeError, KeyError, OSError):
        status = "FAILED"
        store.latch("READONLY_SERVICE_FAILED")
    with store.transaction() as state:
        state["paper_readonly_service_sessions"][identifier].update(
            status=status,
            windows_completed=completed,
            finished_at_utc=datetime.now(UTC).isoformat(),
        )
    result = {
        "status": status,
        "windows_completed": completed,
        "execution_available": False,
        "trial_started": False,
    }
    return result
