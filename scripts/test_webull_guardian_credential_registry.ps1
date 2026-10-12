# Bounded actual guardian-token read of accepted public credential evidence only.
[CmdletBinding()]
param([switch]$PrepareOnly)
$ErrorActionPreference='Stop'
$owner=[Security.Principal.WindowsIdentity]::GetCurrent()
if(-not [Environment]::Is64BitProcess -or -not ([Security.Principal.WindowsPrincipal]::new($owner)).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)){throw 'Elevated 64-bit owner required.'}
$guardian=Get-LocalUser AgenticGuardian
if($guardian.Enabled -or (Get-LocalUser AgenticPaperRuntime).Enabled){throw 'Both accounts must start disabled.'}
$manifest='fbba70f5d4258ef3a56789b03422e796ff7878d6e52734d3b666fb9e18e98e87'
$audit=& (Join-Path $PSScriptRoot 'audit_webull_guardian_release.ps1') -ExpectedManifestSha256 $manifest | ConvertFrom-Json
$python=Join-Path $audit.installed_directory 'python.exe'
$root='C:\ProgramData\AgenticInvestingGuardian';$id=[guid]::NewGuid().ToString('N')
$probePath=Join-Path $root "Code\guardian-credential-registry-$id.py"
$receipt=Join-Path $root "Receipts\guardian-credential-registry-$id.json"
$probe=@'
import json,os,sys
from datetime import UTC,datetime
from pathlib import Path
from security.windows_pipe_identity import NativePipeIdentity
from security.windows_protected_config import ProtectedConfigReader
from security.webull_owner_credential_registry import parse_registry
owner,guardian,identifier=sys.argv[1:4]
if NativePipeIdentity().read_process_identity()!=guardian:raise PermissionError('Actual guardian identity required')
pin='9fe4cf37ee9513eb9668dc2de0997b117abe83704ef0cc79a1c27e38b046b778'
root=Path(r'C:\ProgramData\AgenticInvestingGuardian')
raw=ProtectedConfigReader().read_registry(root/'Code'/('AcceptedOwnerCredential-'+pin+'.json'),owner_sid=owner,guardian_sid=guardian)
parse_registry(raw,expected_sha256=pin,credential_sha256='fc0761142d56f020eac42868d377fb12849458e90a6db5c23edc9bc6ca58e22b',owner_sid=owner,guardian_sid=guardian)
record=dict(schema_version='guardian-credential-registry-fixture-v1',probe_id=identifier,observed_at_utc=datetime.now(UTC).isoformat(),guardian_process_identity_verified=True,held_handle_registry_read_verified=True,binding_signature_verified=True,registry_sha256=pin,review_signature_issued=False,reference_written=False,service_deployed=False,reset_authorized=False,execution_available=False,trial_started=False)
with (root/'Receipts'/('guardian-credential-registry-'+identifier+'.json')).open('x',encoding='utf-8') as stream:
 json.dump(record,stream);stream.flush();os.fsync(stream.fileno())
'@
$stream=[IO.File]::Open($probePath,[IO.FileMode]::CreateNew,[IO.FileAccess]::Write)
try{$bytes=[Text.Encoding]::UTF8.GetBytes($probe);$stream.Write($bytes,0,$bytes.Length);$stream.Flush($true)}finally{$stream.Dispose()}
$admin=[Security.Principal.SecurityIdentifier]::new('S-1-5-32-544');$system=[Security.Principal.SecurityIdentifier]::new('S-1-5-18')
$acl=[Security.AccessControl.FileSecurity]::new();$acl.SetOwner($admin);$acl.SetAccessRuleProtection($true,$false)
foreach($sid in @($admin,$system,$owner.User,$guardian.SID)){
 $rights=if($sid -eq $admin -or $sid -eq $system){'FullControl'}else{'ReadAndExecute'}
 $acl.AddAccessRule([Security.AccessControl.FileSystemAccessRule]::new($sid,$rights,'Allow'))
}
Set-Acl -LiteralPath $probePath -AclObject $acl
function Rules($a){@($a.GetAccessRules($true,$true,[Security.Principal.SecurityIdentifier]) | ForEach-Object {'{0}|{1}|{2}|{3}|{4}|{5}' -f $_.IdentityReference.Value,[int]$_.FileSystemRights,[int]$_.InheritanceFlags,[int]$_.PropagationFlags,[int]$_.AccessControlType,$_.IsInherited} | Sort-Object)}
$actual=Get-Acl -LiteralPath $probePath
if(-not $actual.AreAccessRulesProtected -or $actual.GetOwner([Security.Principal.SecurityIdentifier]) -ne $admin -or (Compare-Object (Rules $acl) (Rules $actual))){throw 'Probe ACL mismatch.'}
& $python -I -B -c 'import pathlib,sys;compile(pathlib.Path(sys.argv[1]).read_bytes(),sys.argv[1],sys.argv[2])' $probePath exec
if($LASTEXITCODE -ne 0){throw 'Probe compilation failed.'}
$probeHash=(Get-FileHash -LiteralPath $probePath).Hash.ToLowerInvariant()
$arguments='-I -B "'+$probePath+'" '+$owner.User.Value+' '+$guardian.SID.Value+' '+$id
if($python.Length+3+$arguments.Length -ge 1024){throw 'Credentialed command line too long.'}
if($PrepareOnly){
 [ordered]@{schema_version='guardian-credential-registry-preparation-v1';probe_path=$probePath;probe_sha256=$probeHash;manifest_sha256=$manifest;probe_compilation_verified=$true;credential_prompted=$false;guardian_disabled=$true;runtime_disabled=$true;process_probe_started=$false;execution_available=$false;trial_started=$false} | ConvertTo-Json
 return
}
$password=Read-Host 'Enter AgenticGuardian password locally (do not share it)' -AsSecureString
$start=[Diagnostics.ProcessStartInfo]::new();$start.FileName=$python;$start.Arguments=$arguments
$start.WorkingDirectory=Join-Path $root 'Logs';$start.UseShellExecute=$false;$start.CreateNoWindow=$true;$start.LoadUserProfile=$false
$start.UserName='AgenticGuardian';$start.Domain=$env:COMPUTERNAME;$start.Password=$password
$start.RedirectStandardError=$true;$start.RedirectStandardOutput=$true;$start.EnvironmentVariables.Clear()
foreach($name in @('SystemRoot','WINDIR')){$start.EnvironmentVariables[$name]=$env:WINDIR}
$start.EnvironmentVariables['PATH']=Join-Path $env:WINDIR 'System32'
foreach($name in @('TEMP','TMP')){$start.EnvironmentVariables[$name]=Join-Path $root 'Logs'}
$process=$null;$stdout=$null;$stderr=$null
try{
 Enable-LocalUser AgenticGuardian
 $process=[Diagnostics.Process]::Start($start);$null=$process.Handle
 $stdout=$process.StandardOutput.ReadToEndAsync();$stderr=$process.StandardError.ReadToEndAsync()
 if(-not $process.WaitForExit(10000)){$process.Kill();throw 'Registry probe exceeded ten-second bound.'}
 $process.WaitForExit()
 if($process.ExitCode -ne 0 -or $stdout.Result.Length -ne 0 -or $stderr.Result.Length -ne 0){throw 'Guardian registry probe failed; diagnostics retained.'}
}finally{
 try{if($process){if(-not $process.HasExited){$process.Kill();$null=$process.WaitForExit(5000)}
  if($process.HasExited){[IO.File]::WriteAllText((Join-Path $root "Logs\guardian-registry-stderr-$id.txt"),$stderr.Result);[IO.File]::WriteAllText((Join-Path $root "Logs\guardian-registry-stdout-$id.txt"),$stdout.Result)}
 }}finally{Disable-LocalUser AgenticGuardian -ErrorAction Stop;$password.Dispose()}
}
$result=Get-Content -LiteralPath $receipt -Raw | ConvertFrom-Json
if($result.probe_id -cne $id -or $result.guardian_process_identity_verified -ne $true -or $result.binding_signature_verified -ne $true -or $result.held_handle_registry_read_verified -ne $true){throw 'Registry probe result mismatch.'}
foreach($flag in @('review_signature_issued','reference_written','service_deployed','reset_authorized','execution_available','trial_started')){if($result.$flag -isnot [bool] -or $result.$flag -ne $false){throw 'Registry probe scope mismatch.'}}
if((Get-LocalUser AgenticGuardian).Enabled -or (Get-LocalUser AgenticPaperRuntime).Enabled -or (Get-FileHash -LiteralPath $probePath).Hash.ToLowerInvariant() -cne $probeHash){throw 'Account/probe state changed.'}
$null=& (Join-Path $PSScriptRoot 'audit_webull_guardian_release.ps1') -ExpectedManifestSha256 $manifest
Write-Output "Guardian credential registry read fixture passed. Both accounts disabled. Evidence: $receipt"
Write-Output 'Public binding verification only; owner app/guardian ceremony, rollback/revocation, provider evidence, reset and trading remain unqualified.'
