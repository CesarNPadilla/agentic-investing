"""Native client startup with the guardian wrapper's restricted environment."""

import json
import os
import subprocess
from pathlib import Path

import pytest

from scripts.check_webull_guardian_failure_paths import CHILD, RELEASE


@pytest.mark.parametrize("scenario", ["partial_frame", "wrong_owner_identity"])
def test_native_failure_client_starts_with_system32_only_path(tmp_path, scenario):
    windows = os.environ["SystemRoot"]
    environment = {
        "SystemRoot": windows,
        "WINDIR": windows,
        "PATH": str(Path(windows) / "System32"),
        "TEMP": str(tmp_path),
        "TMP": str(tmp_path),
    }
    completed = subprocess.run(
        [str(RELEASE / "python.exe"), "-I", "-B", "-c", CHILD, scenario],
        env=environment,
        capture_output=True,
        text=True,
        timeout=8,
        check=False,
        creationflags=subprocess.CREATE_NO_WINDOW,
    )
    assert completed.returncode == 0, completed.stderr
    result = json.loads(completed.stdout)
    assert result["scenario"] == scenario and result["passed"]
    assert result["reference_handler_calls"] == 0
    assert result["pipe_closed"] and result["no_thread_impersonation_token"]
    assert not result["execution_available"]
