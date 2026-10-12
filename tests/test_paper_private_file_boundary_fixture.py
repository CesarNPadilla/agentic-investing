"""Real native file-handle regressions on disposable dummy files only."""

import subprocess
from pathlib import Path

import pytest

from tests.test_paper_directory_authority_fixture import LOAD


def run(script):
    load = LOAD.replace(
        "test_paper_runtime_directory_authority.ps1", "test_paper_runtime_private_file_boundary.ps1"
    ).replace("AgenticDirectoryAccessProbe", "AgenticPrivateFileAccessProbe")
    result = subprocess.run(
        ["powershell.exe", "-NoProfile", "-NonInteractive", "-Command", load + script],
        cwd=Path(__file__).resolve().parents[1],
        capture_output=True,
        text=True,
        timeout=20,
        check=False,
        creationflags=subprocess.CREATE_NO_WINDOW,
    )
    assert result.returncode == 0, "Private-file boundary regression failed"
    assert "FILE-BOUNDARY-CHECK-PASSED" in result.stdout


def test_owner_wrapper_child_and_native_helper_parse():
    run("Write-Output 'FILE-BOUNDARY-CHECK-PASSED'")


@pytest.mark.parametrize("mask", [1, 2, 0x10000, 0x40000, 0x80000])
def test_dummy_file_handle_grants_and_missing_paths_are_distinct(mask):
    run(
        r"""
$path=Join-Path $env:TEMP ('agentic-file-boundary-'+[guid]::NewGuid().ToString('N'))
[IO.File]::WriteAllText($path,'DUMMY-NO-SECRETS')
"""
        + f"$mask=[uint32]{mask};"
        + r"""
try{
 if([AgenticPrivateFileAccessProbe]::OpenExisting($path,$mask) -ne 0){throw 'Positive handle grant failed'}
 $errorCode=[AgenticPrivateFileAccessProbe]::OpenExisting(($path+'.missing'),$mask)
 if($errorCode -ne 2 -and $errorCode -ne 3){throw 'Missing file cannot establish access denied'}
 if([IO.File]::ReadAllText($path) -cne 'DUMMY-NO-SECRETS'){throw 'Handle access changed dummy contents'}
 Write-Output 'FILE-BOUNDARY-CHECK-PASSED'
}finally{[IO.File]::Delete($path)}
"""
    )


def test_explicit_read_data_denial_on_dummy_file():
    run(
        r"""
$path=Join-Path $env:TEMP ('agentic-file-boundary-denial-'+[guid]::NewGuid().ToString('N'))
[IO.File]::WriteAllText($path,'DUMMY-NO-SECRETS')
$original=Get-Acl -LiteralPath $path
$changed=Get-Acl -LiteralPath $path
$identity=[Security.Principal.WindowsIdentity]::GetCurrent()
$changed.AddAccessRule([Security.AccessControl.FileSystemAccessRule]::new($identity.User,'ReadData','Deny'))
try{
 Set-Acl -LiteralPath $path -AclObject $changed
 if([AgenticPrivateFileAccessProbe]::OpenExisting($path,1) -ne 5){throw 'READ_DATA denial not detected'}
 Write-Output 'FILE-BOUNDARY-CHECK-PASSED'
}finally{Set-Acl -LiteralPath $path -AclObject $original;[IO.File]::Delete($path)}
"""
    )
