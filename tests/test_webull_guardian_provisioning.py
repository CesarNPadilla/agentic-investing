"""Exercise provisioning ACLs only in a disposable fixture, never create an account."""

import ctypes
import os
import subprocess
from pathlib import Path

import pytest


@pytest.mark.skipif(not ctypes.windll.shell32.IsUserAnAdmin(), reason="ACL fixture needs elevation")
def test_new_guardian_directory_acl_roundtrip_without_account_provisioning(tmp_path):
    script = r"""
$ErrorActionPreference='Stop'
$tokens=$null;$errors=$null
$ast=[Management.Automation.Language.Parser]::ParseFile((Join-Path $PWD 'scripts/prepare_webull_guardian.ps1'),[ref]$tokens,[ref]$errors)
if($errors.Count){throw 'Provisioning parse failed'}
$function=$ast.Find({param($node) $node -is [Management.Automation.Language.FunctionDefinitionAst] -and $node.Name -eq 'Protect-GuardianDirectory'},$true)
if(-not $function){throw 'ACL helper missing'}
Invoke-Expression $function.Extent.Text
$ownerSid=[Security.Principal.WindowsIdentity]::GetCurrent().User
$adminSid=New-Object Security.Principal.SecurityIdentifier('S-1-5-32-544')
$systemSid=New-Object Security.Principal.SecurityIdentifier('S-1-5-18')
# Existing disabled runtime SID is a fixture substitute, not a guardian assignment.
$guardianSid=(Get-LocalUser -Name AgenticPaperRuntime).SID
$fixtureRoot=[IO.Path]::GetFullPath($env:AGENTIC_GUARDIAN_ACL_FIXTURE)
New-Item -ItemType Directory -Path $fixtureRoot -ErrorAction Stop | Out-Null
Protect-GuardianDirectory $fixtureRoot 'ReadAndExecute'
foreach($entry in @(@{Name='Code';Rights='ReadAndExecute'},@{Name='Config';Rights='ReadAndExecute'},@{Name='References';Rights='Modify'},@{Name='Receipts';Rights='Modify'},@{Name='Logs';Rights='Modify'})){
 $path=Join-Path $fixtureRoot $entry.Name
 New-Item -ItemType Directory -Path $path -ErrorAction Stop | Out-Null
 Protect-GuardianDirectory $path $entry.Rights
 $acl=Get-Acl -LiteralPath $path
 $owner=@($acl.GetAccessRules($true,$true,[Security.Principal.SecurityIdentifier]) | Where-Object {$_.IdentityReference -eq $ownerSid})
 $guardian=@($acl.GetAccessRules($true,$true,[Security.Principal.SecurityIdentifier]) | Where-Object {$_.IdentityReference -eq $guardianSid})
 if($owner.Count -ne 1 -or $owner[0].FileSystemRights -ne ([Security.AccessControl.FileSystemRights]::ReadAndExecute -bor [Security.AccessControl.FileSystemRights]::Synchronize)){throw 'Owner write grant in reference fixture'}
 if($guardian.Count -ne 1 -or $guardian[0].FileSystemRights -ne ([Enum]::Parse([Security.AccessControl.FileSystemRights],$entry.Rights) -bor [Security.AccessControl.FileSystemRights]::Synchronize)){throw 'Guardian fixture rights mismatch'}
}
if((Get-LocalUser -Name AgenticPaperRuntime).Enabled){throw 'Runtime unexpectedly enabled'}
Write-Output 'GARDIAN-ACL-ROUNDTRIP-PASSED'
"""
    environment = dict(
        os.environ, AGENTIC_GUARDIAN_ACL_FIXTURE=str(tmp_path / "guardian-acl-fixture")
    )
    result = subprocess.run(
        ["powershell.exe", "-NoProfile", "-NonInteractive", "-Command", script],
        cwd=Path(__file__).resolve().parents[1],
        env=environment,
        capture_output=True,
        text=True,
        timeout=20,
        check=False,
        creationflags=subprocess.CREATE_NO_WINDOW,
    )
    assert result.returncode == 0, result.stderr
    assert "GARDIAN-ACL-ROUNDTRIP-PASSED" in result.stdout
