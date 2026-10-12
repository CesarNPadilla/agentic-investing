"""Regression for the diagnostic pipe label setter and explicit client access mask."""

import subprocess
from pathlib import Path


def test_medium_label_readback_and_client_connection():
    root = Path(__file__).resolve().parents[1]
    script = r"""
$ErrorActionPreference='Stop'
. .\scripts\paper_pipe_fixture_security.ps1
$tokens=$null;$errors=$null
$ast=[Management.Automation.Language.Parser]::ParseFile((Join-Path $PWD 'scripts/test_paper_runtime_pipe_identity.ps1'),[ref]$tokens,[ref]$errors)
if($errors.Count){throw 'Wrapper syntax failed'}
$assignment=$ast.Find({param($node) $node -is [Management.Automation.Language.AssignmentStatementAst] -and $node.Left.Extent.Text -eq '$childText'},$true)
$childTokens=$null;$childErrors=$null
[Management.Automation.Language.Parser]::ParseInput($assignment.Right.Expression.Value,[ref]$childTokens,[ref]$childErrors) | Out-Null
if($childErrors.Count){throw 'Child syntax failed'}
$server=$client=$null
try{
 $name='AgenticMediumRegression-'+[guid]::NewGuid().ToString('N')
 $identity=[Security.Principal.WindowsIdentity]::GetCurrent()
 $security=New-Object IO.Pipes.PipeSecurity
 $security.SetAccessRuleProtection($true,$false)
 $security.SetOwner($identity.User)
 $security.AddAccessRule([IO.Pipes.PipeAccessRule]::new($identity.User,[IO.Pipes.PipeAccessRights]::FullControl,[Security.AccessControl.AccessControlType]::Allow))
 $server=[IO.Pipes.NamedPipeServerStream]::new($name,[IO.Pipes.PipeDirection]::InOut,1,[IO.Pipes.PipeTransmissionMode]::Byte,[IO.Pipes.PipeOptions]::Asynchronous,4096,4096,$security,[IO.HandleInheritability]::None,[IO.Pipes.PipeAccessRights]::TakeOwnership)
 $label=Set-PaperFixturePipeMediumLabel -Pipe $server
 if(-not $label.MediumLabelVerified){throw 'Medium label verification failed'}
 $pending=$server.BeginWaitForConnection($null,$null)
 $rights=[IO.Pipes.PipeAccessRights]::ReadData -bor [IO.Pipes.PipeAccessRights]::WriteData -bor [IO.Pipes.PipeAccessRights]::Synchronize
 if(([int]$rights -band [int][IO.Pipes.PipeAccessRights]::CreateNewInstance) -ne 0){throw 'Client must not request instance-creation authority'}
 $client=[IO.Pipes.NamedPipeClientStream]::new('.',$name,$rights,[IO.Pipes.PipeOptions]::None,[Security.Principal.TokenImpersonationLevel]::Identification,[IO.HandleInheritability]::None)
 $client.Connect(2000)
 if(-not $pending.AsyncWaitHandle.WaitOne(2000)){throw 'Fixture connection failed'}
 $server.EndWaitForConnection($pending)
 $client.WriteByte(1)
 $buffer=New-Object byte[] 1
 $read=$server.ReadAsync($buffer,0,1)
 if(-not $read.Wait(2000) -or $read.Result -ne 1 -or $buffer[0] -ne 1){throw 'Fixture message failed'}
 Write-Output 'MEDIUM-LABEL-AND-CONNECTION-PASSED'
}finally{if($client){$client.Dispose()};if($server){$server.Dispose()}}
"""
    result = subprocess.run(
        ["powershell.exe", "-NoProfile", "-NonInteractive", "-Command", script],
        cwd=root,
        capture_output=True,
        text=True,
        timeout=15,
        check=False,
        creationflags=subprocess.CREATE_NO_WINDOW,
    )
    assert result.returncode == 0, "Disposable pipe label/connection regression failed"
    assert "MEDIUM-LABEL-AND-CONNECTION-PASSED" in result.stdout


def test_restrictive_pipe_acl_requires_read_attributes():
    root = Path(__file__).resolve().parents[1]
    script = r"""
$ErrorActionPreference='Stop'
foreach($includeAttributes in @($false,$true)){
 $identity=[Security.Principal.WindowsIdentity]::GetCurrent()
 $rights=[IO.Pipes.PipeAccessRights]::ReadData -bor [IO.Pipes.PipeAccessRights]::WriteData -bor [IO.Pipes.PipeAccessRights]::Synchronize
 $grant=$rights
 if($includeAttributes){$grant=$grant -bor [IO.Pipes.PipeAccessRights]::ReadAttributes}
 if(([int]$grant -band [int][IO.Pipes.PipeAccessRights]::CreateNewInstance) -ne 0){throw 'Unexpected instance creation authority'}
 $security=New-Object IO.Pipes.PipeSecurity
 $security.SetAccessRuleProtection($true,$false)
 $security.SetOwner($identity.User)
 # No FullControl grant: the connection must work using only these limited rights.
 $security.AddAccessRule([IO.Pipes.PipeAccessRule]::new($identity.User,$grant,[Security.AccessControl.AccessControlType]::Allow))
 $server=$client=$null
 try{
  $name='AgenticRestrictedAclRegression-'+[guid]::NewGuid().ToString('N')
  $server=[IO.Pipes.NamedPipeServerStream]::new($name,[IO.Pipes.PipeDirection]::InOut,1,[IO.Pipes.PipeTransmissionMode]::Byte,[IO.Pipes.PipeOptions]::Asynchronous,4096,4096,$security)
  $pending=$server.BeginWaitForConnection($null,$null)
  $client=[IO.Pipes.NamedPipeClientStream]::new('.',$name,$rights,[IO.Pipes.PipeOptions]::None,[Security.Principal.TokenImpersonationLevel]::Identification,[IO.HandleInheritability]::None)
  $connected=$false
  try{$client.Connect(1000);$connected=$true}catch [UnauthorizedAccessException]{}
  if($connected){if(-not $pending.AsyncWaitHandle.WaitOne(1000)){throw 'Connect deadline failed'};$server.EndWaitForConnection($pending)}
  if($connected -ne $includeAttributes){throw 'Restricted ACL regression expectation failed'}
 }finally{if($client){$client.Dispose()};if($server){$server.Dispose()}}
}
Write-Output 'RESTRICTED-ACL-DENIAL-AND-FIX-PASSED'
"""
    result = subprocess.run(
        ["powershell.exe", "-NoProfile", "-NonInteractive", "-Command", script],
        cwd=root,
        capture_output=True,
        text=True,
        timeout=10,
        check=False,
        creationflags=subprocess.CREATE_NO_WINDOW,
    )
    assert result.returncode == 0, "Restrictive pipe ACL regression failed"
    assert "RESTRICTED-ACL-DENIAL-AND-FIX-PASSED" in result.stdout
