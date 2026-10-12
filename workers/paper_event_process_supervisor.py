"""Bounded process watchdog for read-only event/timer checks; no broker mutation."""

import json
import queue
import re
import subprocess
import threading
import time
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

from risk.paper_state import PaperState
from workers.windows_child_job import WindowsChildJob


def supervise_events(
    root,
    *,
    env_file,
    ledger_file,
    owner_credential_file,
    seconds=5,
    timeout_seconds=5,
    process_factory=subprocess.Popen,
    job_factory=WindowsChildJob,
):
    if type(seconds) is not int or not 1 <= seconds <= 60 or not 0 < timeout_seconds <= 5:
        raise ValueError("Bounded read-only event supervision required")
    root = Path(root).resolve()
    paths = [Path(path).resolve() for path in (env_file, ledger_file, owner_credential_file)]
    if any(path.is_relative_to(root) for path in paths):
        raise ValueError("Private inputs must be outside repository")
    store = PaperState(paths[1])
    session = str(uuid4())
    with store.transaction() as state:
        sessions = state.setdefault("paper_event_process_sessions", {})
        if "EVENT_PROCESS_WATCHDOG_FAILED" in state["latch_reasons"] or any(
            row.get("completed") is not True for row in sessions.values()
        ):
            return {
                "blockers": ["EVENT_PROCESS_RECOVERY_REQUIRED"],
                "execution_available": False,
                "trial_started": False,
            }
        sessions[session] = {"started_at_utc": datetime.now(UTC).isoformat(), "completed": False}
    process = None
    job = None
    gate = paths[1].parent / ("paper-child-gate-" + uuid4().hex)
    token = uuid4().hex
    gate_created = False
    messages = queue.Queue(maxsize=16)
    checks = 0
    latest = None
    blockers = set()
    try:
        command = [
            str(root / ".venv/Scripts/python.exe"),
            "-m",
            "scripts.observe_paper_events",
            "--env-file",
            str(paths[0]),
            "--ledger-file",
            str(paths[1]),
            "--owner-credential-file",
            str(paths[2]),
            "--seconds",
            str(seconds),
            "--heartbeat-lines",
            "--startup-gate",
            str(gate),
            "--startup-token",
            token,
        ]
        started = time.monotonic()
        job = job_factory()
        process = process_factory(
            command,
            cwd=root,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            text=True,
            creationflags=subprocess.CREATE_NO_WINDOW,
        )
        job.attach(process)
        with gate.open("x", encoding="ascii") as handle:
            handle.write(token)
        gate_created = True

        def read_output():
            try:
                while True:
                    line = process.stdout.readline(65537)
                    if not line:
                        messages.put_nowait((time.monotonic(), None))
                        break
                    if len(line) > 65536:
                        raise ValueError("Oversized child message")
                    messages.put_nowait((time.monotonic(), json.loads(line)))
            except (ValueError, OSError, queue.Full):
                try:
                    messages.put_nowait((time.monotonic(), None))
                except queue.Full:
                    pass  # Full queues cannot establish fresh successful checks.

        threading.Thread(target=read_output, daemon=True).start()
        deadline = started + timeout_seconds
        absolute_deadline = started + seconds + 15
        while True:
            remaining = min(deadline, absolute_deadline) - time.monotonic()
            if remaining <= 0:
                raise TimeoutError("Child monitoring deadline")
            received, row = messages.get(timeout=remaining)
            if received > deadline or time.monotonic() - received >= timeout_seconds:
                raise TimeoutError("Late child observation")
            if (
                not isinstance(row, dict)
                or row.get("execution_available") is not False
                or row.get("trial_started") is not False
            ):
                raise ValueError("Unqualified child state")
            if row.get("kind") == "check":
                if (
                    type(row.get("sequence")) is not int
                    or row["sequence"] != checks + 1
                    or row.get("account_observed") is not True
                    or not isinstance(row.get("blockers"), list)
                    or any(
                        not isinstance(x, str) or not re.fullmatch(r"[A-Z0-9_]{1,100}", x)
                        for x in row["blockers"]
                    )
                ):
                    raise ValueError("Invalid check receipt")
                checks += 1
                blockers.update(row["blockers"])
                deadline = received + timeout_seconds
            elif row.get("kind") == "complete":
                if (
                    not checks
                    or type(row.get("diagnostic_cycles")) is not int
                    or row.get("diagnostic_cycles") != checks
                    or not isinstance(row.get("stream"), dict)
                    or not isinstance(row.get("latest_diagnostic"), dict)
                    or row.get("stream", {}).get("monitor_completed") is not True
                    or row.get("latest_diagnostic", {}).get("account_observed") is not True
                    or row.get("latest_diagnostic", {}).get("execution_available") is not False
                    or row.get("latest_diagnostic", {}).get("trial_started") is not False
                ):
                    raise ValueError("Incomplete event monitor")
                latest = row
                break
            else:
                raise ValueError("Child monitor failed")
        process.wait(timeout=min(timeout_seconds, max(0.001, deadline - time.monotonic())))
        if process.returncode != 0:
            raise ValueError("Child did not exit successfully")
        with store.transaction() as state:
            state["paper_event_process_sessions"][session].update(
                completed=True,
                checks_completed=checks,
                finished_at_utc=datetime.now(UTC).isoformat(),
            )
        return {
            "monitor_completed": True,
            "checks_completed": checks,
            "blockers": sorted(blockers),
            "latest_diagnostic": latest["latest_diagnostic"],
            "execution_available": False,
            "trial_started": False,
        }
    except (
        OSError,
        ValueError,
        TypeError,
        RuntimeError,
        TimeoutError,
        queue.Empty,
        subprocess.SubprocessError,
    ):
        terminated = process is None
        if process is not None:
            process.kill()
            try:
                process.wait(timeout=2)
                terminated = process.poll() is not None
            except subprocess.TimeoutExpired:
                terminated = False
        store.latch("EVENT_PROCESS_WATCHDOG_FAILED")
        return {
            "monitor_completed": False,
            "child_terminated": terminated,
            "blockers": ["EVENT_PROCESS_WATCHDOG_FAILED"],
            "execution_available": False,
            "trial_started": False,
        }
    finally:
        if job is not None:
            job.close()
        if gate_created:
            gate.unlink(missing_ok=True)
