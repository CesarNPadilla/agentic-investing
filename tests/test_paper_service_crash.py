"""Actual process death must preserve an unfinished diagnostic service claim."""

import subprocess
import sys
import time
from pathlib import Path

from risk.paper_state import PaperState
from workers.paper_readonly_service import run_service


def test_killed_service_blocks_restart_without_source_access(tmp_path):
    ledger = tmp_path / "state.sqlite"
    marker = tmp_path / "entered-window"
    state = PaperState.initialize(ledger, account_binding="a" * 64)
    code = """
import sys,time
from pathlib import Path
from risk.paper_state import PaperState
from workers.paper_readonly_service import run_service
def window():
    Path(sys.argv[2]).write_text('claimed', encoding='utf-8')
    time.sleep(60)
run_service(PaperState(sys.argv[1]), window,
            regular_session=lambda: True, stop_requested=lambda: False)
"""
    process = subprocess.Popen(
        [sys.executable, "-c", code, str(ledger), str(marker)],
        cwd=Path(__file__).resolve().parents[1],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
    )
    try:
        deadline = time.monotonic() + 5
        while not marker.exists() and time.monotonic() < deadline:
            assert process.poll() is None
            time.sleep(0.02)
        assert marker.exists(), "Service never reached its durably claimed window"
        process.kill()
        process.wait(timeout=5)
        sessions = state.read()["paper_readonly_service_sessions"]
        assert len(sessions) == 1
        assert next(iter(sessions.values()))["status"] == "RUNNING"

        def forbidden_source():
            raise AssertionError("An interrupted service must not contact sources")

        result = run_service(
            state, forbidden_source, regular_session=lambda: True, stop_requested=lambda: False
        )
        assert result["status"] == "RECOVERY_REQUIRED"
        assert state.read()["paper_readonly_service_sessions"] == sessions
        assert state.read()["latched"] is True
        assert result["execution_available"] is False
        assert result["trial_started"] is False
    finally:
        if process.poll() is None:
            process.kill()
        process.wait(timeout=5)
