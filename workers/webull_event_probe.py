"""Bounded diagnostic child containment; no trading or replay qualification."""

import json
import subprocess
from pathlib import Path
from uuid import uuid4

from workers.windows_child_job import WindowsChildJob


def supervise_probe(
    root,
    env_file,
    selection_file,
    *,
    seconds=35,
    process_factory=subprocess.Popen,
    job_factory=WindowsChildJob,
):
    if type(seconds) is not int or not 1 <= seconds <= 45:
        raise ValueError("Diagnostic duration must be 1..45 seconds")
    root = Path(root).resolve()
    env_file, selection_file = Path(env_file).resolve(), Path(selection_file).resolve()
    if any(p.is_relative_to(root) for p in (env_file, selection_file)):
        raise ValueError("Private inputs must stay outside repository")
    report = selection_file.parent / ("webull-event-observation-" + uuid4().hex + ".json")
    gate = report.with_suffix(".gate")
    process = job = None
    termination = "CHILD_EXITED"
    try:
        job = job_factory()
        process = process_factory(
            [
                str(root / ".venv/Scripts/python.exe"),
                "-m",
                "scripts.probe_webull_events",
                "--env-file",
                str(env_file),
                "--selection-file",
                str(selection_file),
                "--child-report",
                str(report),
                "--startup-gate",
                str(gate),
            ],
            cwd=root,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            creationflags=subprocess.CREATE_NO_WINDOW,
        )
        job.attach(process)
        # Credentials/network are not used by the child until containment succeeds.
        with gate.open("x") as handle:
            handle.write("CONTAINED_DIAGNOSTIC")
        try:
            process.wait(timeout=seconds)
        except subprocess.TimeoutExpired:
            termination = "DEADLINE_TERMINATED"
        finally:
            job.close()
            job = None
            process.wait(timeout=5)
        evidence = json.loads(report.read_text())
        if (
            evidence.get("schema_version") != "webull-event-observation-v1"
            or evidence.get("execution_available") is not False
            or evidence.get("trial_started") is not False
        ):
            raise ValueError("Diagnostic child evidence invalid")
        evidence.update(
            termination=termination,
            child_exit_code=process.returncode,
            child_contained=True,
            maximum_observation_seconds=seconds,
            missed_event_coverage=False,
            continuous_supervision_qualified=False,
        )
        return evidence
    finally:
        try:
            if job is not None:
                job.close()
        finally:
            if process is not None and process.poll() is None:
                process.kill()
                process.wait(timeout=5)
            if gate.exists():
                gate.unlink()
