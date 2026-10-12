import subprocess
from pathlib import Path

import pytest

from tests.test_paper_directory_authority_fixture import LOAD


def run(script):
    load = LOAD.replace(
        "test_paper_runtime_directory_authority.ps1", "test_paper_runtime_process_environment.ps1"
    )
    result = subprocess.run(
        ["powershell.exe", "-NoProfile", "-NonInteractive", "-Command", load + script],
        cwd=Path(__file__).resolve().parents[1],
        capture_output=True,
        text=True,
        timeout=20,
        check=False,
        creationflags=subprocess.CREATE_NO_WINDOW,
    )
    assert result.returncode == 0, "Process/environment fixture regression failed"
    assert "PROCESS-PROBE-PASSED" in result.stdout


def test_owner_wrapper_embedded_client_and_native_helper_parse():
    run("Write-Output 'PROCESS-PROBE-PASSED'")


@pytest.mark.parametrize("mask", [0x10, 0x20, 8, 2, 0x40, 0x40000, 0x80000])
def test_current_process_grants_can_be_observed_without_using_authority(mask):
    run(
        f"if([AgenticProcessAccessProbe]::Probe([uint32]$PID,[uint32]{mask}) -ne 0)"
        "{throw 'Current process positive grant failed'};Write-Output 'PROCESS-PROBE-PASSED'"
    )


def test_invalid_process_id_is_not_access_denied():
    run(
        "if([AgenticProcessAccessProbe]::Probe(0,0x10) -ne 87)"
        "{throw 'Invalid process ID must not establish access denied'};Write-Output 'PROCESS-PROBE-PASSED'"
    )
