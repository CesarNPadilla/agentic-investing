"""Exercise the owner's diagnostic native helper without enabling the runtime."""

import subprocess
from pathlib import Path

import pytest

LOAD = r"""
$ErrorActionPreference='Stop'
$tokens=$null;$errors=$null
$ast=[Management.Automation.Language.Parser]::ParseFile((Join-Path $PWD 'scripts/test_paper_runtime_directory_authority.ps1'),[ref]$tokens,[ref]$errors)
if($errors.Count){throw 'Wrapper parse failed'}
$assignment=$ast.Find({param($node) $node -is [Management.Automation.Language.AssignmentStatementAst] -and $node.Left.Extent.Text -eq '$childText'},$true)
$childTokens=$null;$childErrors=$null
$child=[Management.Automation.Language.Parser]::ParseInput($assignment.Right.Expression.Value,[ref]$childTokens,[ref]$childErrors)
if($childErrors.Count){throw 'Client parse failed'}
$definition=$child.Find({param($node) $node -is [Management.Automation.Language.CommandAst] -and $node.GetCommandName() -eq 'Add-Type'},$true)
Add-Type -TypeDefinition $definition.CommandElements[-1].Value
"""


def run(script):
    result = subprocess.run(
        ["powershell.exe", "-NoProfile", "-NonInteractive", "-Command", LOAD + script],
        cwd=Path(__file__).resolve().parents[1],
        capture_output=True,
        text=True,
        timeout=20,
        check=False,
        creationflags=subprocess.CREATE_NO_WINDOW,
    )
    assert result.returncode == 0, "Directory authority regression failed"
    assert "AUTHORITY-CHECK-PASSED" in result.stdout


def test_wrapper_client_and_native_definition_parse():
    run("Write-Output 'AUTHORITY-CHECK-PASSED'")


@pytest.mark.parametrize("mask", [0x40000, 0x80000, 0xC0000])
def test_owned_directory_grant_and_missing_path_are_not_denials(mask):
    run(
        r"""
$path=Join-Path $env:TEMP ('agentic-directory-regression-'+[guid]::NewGuid().ToString('N'))
New-Item -ItemType Directory -Path $path | Out-Null
"""
        + f"$mask=[uint32]{mask};"
        + r"""
try{
 if([AgenticDirectoryAccessProbe]::OpenExisting($path,$mask) -ne 0){throw 'Positive grant failed'}
 $errorCode=[AgenticDirectoryAccessProbe]::OpenExisting((Join-Path $path 'missing'),$mask)
 if($errorCode -ne 2 -and $errorCode -ne 3){throw 'Missing path must not be accepted as access denied'}
 Write-Output 'AUTHORITY-CHECK-PASSED'
}finally{[IO.Directory]::Delete($path)}
"""
    )


def test_explicit_ownership_denial_is_detected_on_disposable_directory():
    run(
        r"""
$path=Join-Path $env:TEMP ('agentic-directory-denial-'+[guid]::NewGuid().ToString('N'))
New-Item -ItemType Directory -Path $path | Out-Null
$original=Get-Acl -LiteralPath $path
$changed=Get-Acl -LiteralPath $path
$identity=[Security.Principal.WindowsIdentity]::GetCurrent()
$changed.AddAccessRule([Security.AccessControl.FileSystemAccessRule]::new($identity.User,'TakeOwnership','Deny'))
try{
 Set-Acl -LiteralPath $path -AclObject $changed
 if([AgenticDirectoryAccessProbe]::OpenExisting($path,0x80000) -ne 5){throw 'Explicit WRITE_OWNER denial not detected'}
 Write-Output 'AUTHORITY-CHECK-PASSED'
}finally{Set-Acl -LiteralPath $path -AclObject $original;[IO.Directory]::Delete($path)}
"""
    )
