"""Process-level watchdog for the fixed read-only observer, never an order runner."""

import json
import subprocess
import time
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

from risk.paper_state import PaperState


def run_readonly_cycle(
    root, *, env_file, ledger_file, timeout_seconds=5, process_factory=subprocess.Popen
):
    if not 0 < timeout_seconds <= 5:
        raise ValueError("Read-only process deadline must be within five seconds")
    root, ledger_file = Path(root).resolve(), Path(ledger_file).resolve()
    if ledger_file.is_relative_to(root):
        raise ValueError("Private state must be outside repository")
    store = PaperState(ledger_file)
    if "READONLY_PROCESS_DEADLINE_MISSED" in store.read()["latch_reasons"]:
        return {
            "blockers": ["READONLY_PROCESS_RECOVERY_REQUIRED"],
            "execution_available": False,
            "trial_started": False,
        }
    # Fixed module and arguments: no generic shell, broker mutation, or user-provided command.
    command = [
        str(root / ".venv/Scripts/python.exe"),
        "-m",
        "scripts.observe_paper_trial",
        "--env-file",
        str(Path(env_file).resolve()),
        "--ledger-file",
        str(ledger_file),
        "--cycles",
        "1",
        "--interval-seconds",
        "5",
    ]
    process = process_factory(
        command,
        cwd=root,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        creationflags=subprocess.CREATE_NO_WINDOW,
    )
    try:
        stdout, _ = process.communicate(timeout=timeout_seconds)
    except subprocess.TimeoutExpired:
        blockers = ["READONLY_PROCESS_DEADLINE_MISSED"]
        process.kill()
        try:
            process.communicate(timeout=2)
        except subprocess.TimeoutExpired:
            blockers.append("READONLY_PROCESS_TERMINATION_UNVERIFIED")
        # Terminate the read-only writer before latching to release its SQLite locks.
        store.latch("READONLY_PROCESS_DEADLINE_MISSED")
        return {
            "blockers": blockers,
            "child_terminated": process.poll() is not None,
            "execution_available": False,
            "trial_started": False,
        }
    try:
        reports = json.loads(stdout)
        if (
            process.returncode != 0
            or not isinstance(reports, list)
            or len(reports) != 1
            or not isinstance(reports[0], dict)
            or reports[0].get("execution_available") is not False
            or reports[0].get("trial_started") is not False
            or reports[0].get("account_observed") is not True
            or not isinstance(reports[0].get("blockers"), list)
            or any(not isinstance(reason, str) for reason in reports[0]["blockers"])
        ):
            raise ValueError("Unqualified child observation")
    except (ValueError, TypeError):
        store.latch("READONLY_PROCESS_FAILED")
        return {
            "blockers": ["READONLY_PROCESS_FAILED"],
            "execution_available": False,
            "trial_started": False,
        }
    return {
        "child_terminated": True,
        "report": reports[0],
        "blockers": reports[0]["blockers"],
        "execution_available": False,
        "trial_started": False,
    }


def run_supervised_batch(
    root,
    *,
    env_file,
    ledger_file,
    cycles=3,
    interval_seconds=5,
    cycle_runner=run_readonly_cycle,
    monotonic=time.monotonic,
    sleep=time.sleep,
):
    if type(cycles) is not int or not 1 <= cycles <= 12 or not 1 <= interval_seconds <= 5:
        raise ValueError("Bounded read-only supervision required")
    if Path(ledger_file).resolve().is_relative_to(Path(root).resolve()):
        raise ValueError("Private state must be outside repository")
    store = PaperState(ledger_file)
    identifier = str(uuid4())
    with store.transaction() as state:
        sessions = state.setdefault("paper_supervisor_sessions", {})
        if any(row.get("completed") is not True for row in sessions.values()):
            return {
                "blockers": ["READONLY_SUPERVISOR_RECOVERY_REQUIRED"],
                "execution_available": False,
                "trial_started": False,
            }
        sessions[identifier] = {
            "started_at": datetime.now(UTC).isoformat(),
            "completed": False,
            "cycles_completed": 0,
        }
    reports = []
    try:
        for index in range(cycles):
            started = monotonic()
            report = cycle_runner(root, env_file=env_file, ledger_file=ledger_file)
            reports.append(report)
            if "report" not in report or report.get("execution_available") is not False:
                break
            with store.transaction() as state:
                state["paper_supervisor_sessions"][identifier]["cycles_completed"] = index + 1
            elapsed = monotonic() - started
            if elapsed < 0:
                raise ValueError("Supervisor monotonic clock regressed")
            if index + 1 < cycles:
                sleep(max(0, interval_seconds - elapsed))
        completed = len(reports) == cycles and all("report" in r for r in reports)
        with store.transaction() as state:
            state["paper_supervisor_sessions"][identifier].update(
                completed=completed, finished_at=datetime.now(UTC).isoformat()
            )
        if not completed:
            store.latch("READONLY_SUPERVISED_BATCH_FAILED")
        return {
            "batch_completed": completed,
            "reports": reports,
            "execution_available": False,
            "trial_started": False,
        }
    except (RuntimeError, ValueError, TypeError, OSError):
        store.latch("READONLY_SUPERVISED_BATCH_FAILED")
        return {
            "blockers": ["READONLY_SUPERVISED_BATCH_FAILED"],
            "execution_available": False,
            "trial_started": False,
        }
