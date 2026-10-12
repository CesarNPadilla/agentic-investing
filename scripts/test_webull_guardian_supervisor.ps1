# Actual guardian-token synthetic process supervision. No reference/signature/service/broker.
[CmdletBinding()]
param([switch]$PrepareOnly)
$ErrorActionPreference='Stop'
$owner=[Security.Principal.WindowsIdentity]::GetCurrent()
if(-not [Environment]::Is64BitProcess -or -not ([Security.Principal.WindowsPrincipal]::new($owner)).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)){throw 'Elevated 64-bit owner PowerShell required.'}
$guardian=Get-LocalUser AgenticGuardian
if($guardian.Enabled -or (Get-LocalUser AgenticPaperRuntime).Enabled){throw 'Both accounts must start disabled.'}
$pin='5deef8dd171e545944d13f8f79d610c0c7c9bdbd33e27685a1fb6d53f4a818ea'
$audit=& (Join-Path $PSScriptRoot 'audit_webull_guardian_release.ps1') -ExpectedManifestSha256 $pin | ConvertFrom-Json
$root='C:\ProgramData\AgenticInvestingGuardian'
$id=[guid]::NewGuid().ToString('N')
$receipt=Join-Path $root "Receipts\guardian-supervisor-$id.json"
$probe=@'
import hashlib,json,os,sys
from datetime import UTC,datetime
from pathlib import Path
from security.windows_pipe_identity import NativePipeIdentity
from security.windows_review_process_supervisor import supervise_review_process
expected,identifier=sys.argv[1:3]
if NativePipeIdentity().read_process_identity()!=expected:
 raise PermissionError('Configured guardian process required')
root=Path(r'C:\ProgramData\AgenticInvestingGuardian')
python=Path(sys.executable)
identity_code="import sys;from security.windows_pipe_identity import NativePipeIdentity;assert NativePipeIdentity().read_process_identity()==sys.argv[1];raise SystemExit(7)"
cases=[(['-I','-B','-c',identity_code,expected],5,False),
       (['-I','-c','import time;time.sleep(60)'],0.2,False),
       (['-I','-c','import time;time.sleep(60)'],5,True),
       (['-I','-c',"import subprocess,sys;subprocess.Popen([sys.executable,'-I','-c','import time;time.sleep(60)'])"],5,False)]
results=[]
for args,seconds,stop in cases:
 results.append(supervise_review_process(python,args,root/'Logs',seconds=seconds,stop_requested=lambda:stop))
if results[0]['exit_code']!=7 or results[1]['termination']!='DEADLINE_TERMINATED' or results[2]['termination']!='STOP_REQUESTED' or any(r['process_tree_active']!=0 for r in results):
 raise ValueError('Synthetic supervision result rejected')
record={'schema_version':'guardian-native-supervisor-fixture-v1','probe_id':identifier,
        'observed_at_utc':datetime.now(UTC).isoformat(),'guardian_process_identity_verified':True,
        'contained_child_identity_verified':True,'cases':results,'real_reference_used':False,
        'service_deployed':False,'execution_available':False,'reset_authorized':False,'trial_started':False}
with (root/'Receipts'/('guardian-supervisor-'+identifier+'.json')).open('x',encoding='utf-8') as stream:
 json.dump(record,stream);stream.flush();os.fsync(stream.fileno())
print('GUARDIAN_NATIVE_SUPERVISION_COMPLETE_SYNTHETIC_ONLY')
'@
$probeBytes=[Text.Encoding]::UTF8.GetBytes($probe)
$digest=[Security.Cryptography.SHA256]::Create()
try{$probeHash=([BitConverter]::ToString($digest.ComputeHash($probeBytes))).Replace('-','').ToLowerInvariant()}finally{$digest.Dispose()}
# Credentialed Windows launch has a 1024-character command-line limit.
# Retain the literal in a fresh protected ordinary file, rather than passing it inline.
$codeParent=Join-Path $root 'Code'
$admin=[Security.Principal.SecurityIdentifier]::new('S-1-5-32-544')
$system=[Security.Principal.SecurityIdentifier]::new('S-1-5-18')
$parentAcl=Get-Acl -LiteralPath $codeParent
if(-not $parentAcl.AreAccessRulesProtected -or $parentAcl.GetOwner([Security.Principal.SecurityIdentifier]) -ne $admin -or ((Get-Item -LiteralPath $codeParent).Attributes -band [IO.FileAttributes]::ReparsePoint)){throw 'Protected ordinary Code parent required.'}
$probePath=Join-Path $codeParent "guardian-supervisor-$id.py"
$stream=[IO.File]::Open($probePath,[IO.FileMode]::CreateNew,[IO.FileAccess]::Write)
try{$stream.Write($probeBytes,0,$probeBytes.Length);$stream.Flush($true)}finally{$stream.Dispose()}
$probeAcl=[Security.AccessControl.FileSecurity]::new()
$probeAcl.SetOwner($admin);$probeAcl.SetAccessRuleProtection($true,$false)
foreach($sid in @($admin,$system,$owner.User,$guardian.SID)){
 $rights=if($sid -eq $admin -or $sid -eq $system){'FullControl'}else{'ReadAndExecute'}
 $probeAcl.AddAccessRule([Security.AccessControl.FileSystemAccessRule]::new($sid,$rights,'Allow'))
}
Set-Acl -LiteralPath $probePath -AclObject $probeAcl
function Probe-Rules($Acl){@($Acl.GetAccessRules($true,$true,[Security.Principal.SecurityIdentifier]) | ForEach-Object {'{0}|{1}|{2}|{3}|{4}|{5}' -f $_.IdentityReference.Value,[int]$_.FileSystemRights,[int]$_.InheritanceFlags,[int]$_.PropagationFlags,[int]$_.AccessControlType,$_.IsInherited} | Sort-Object)}
function Assert-Probe{
 $actual=Get-Acl -LiteralPath $probePath
 if(-not $actual.AreAccessRulesProtected -or $actual.GetOwner([Security.Principal.SecurityIdentifier]) -ne $admin -or (Compare-Object (Probe-Rules $probeAcl) (Probe-Rules $actual)) -or ((Get-Item -LiteralPath $probePath).Attributes -band [IO.FileAttributes]::ReparsePoint) -or (Get-FileHash -LiteralPath $probePath -Algorithm SHA256).Hash.ToLowerInvariant() -cne $probeHash){throw 'Protected probe hash/ACL check failed.'}
}
Assert-Probe
$executable=Join-Path $audit.installed_directory 'python.exe'
$arguments='-I -B "'+$probePath+'" '+$guardian.SID.Value+' '+$id
$commandLineCharacters=$executable.Length+3+$arguments.Length
if($commandLineCharacters -ge 1024){throw 'Credentialed command line exceeds safe bound.'}
& $executable -I -B -c 'import pathlib,sys;compile(pathlib.Path(sys.argv[1]).read_bytes(),sys.argv[1],sys.argv[2])' $probePath exec
if($LASTEXITCODE -ne 0){throw 'Protected probe compilation failed.'}
if($PrepareOnly){
 [ordered]@{schema_version='guardian-supervisor-source-preparation-v1';probe_path=$probePath;probe_sha256=$probeHash;command_line_characters=$commandLineCharacters;protected_probe_verified=$true;probe_compilation_verified=$true;guardian_disabled=$true;runtime_disabled=$true;credential_prompted=$false;process_probe_started=$false} | ConvertTo-Json
 return
}
$password=Read-Host 'Enter AgenticGuardian password locally (do not share it)' -AsSecureString
$start=[Diagnostics.ProcessStartInfo]::new()
$start.FileName=$executable
$start.Arguments=$arguments
$start.WorkingDirectory=Join-Path $root 'Logs';$start.UseShellExecute=$false;$start.CreateNoWindow=$true;$start.LoadUserProfile=$false
$start.UserName='AgenticGuardian';$start.Domain=$env:COMPUTERNAME;$start.Password=$password
$start.RedirectStandardError=$true;$start.RedirectStandardOutput=$true
$start.EnvironmentVariables.Clear()
foreach($name in @('SystemRoot','WINDIR')){$start.EnvironmentVariables[$name]=$env:WINDIR}
$start.EnvironmentVariables['PATH']=Join-Path $env:WINDIR 'System32'
foreach($name in @('TEMP','TMP')){$start.EnvironmentVariables[$name]=Join-Path $root 'Logs'}
$process=$null
try{
 Enable-LocalUser AgenticGuardian
 $process=[Diagnostics.Process]::Start($start);$null=$process.Handle
 if(-not $process.WaitForExit(25000)){throw 'Guardian supervision probe exceeded outer wait; diagnostics retained.'}
 $process.WaitForExit()
 if($null -eq $process.ExitCode -or $process.ExitCode -ne 0){throw 'Guardian supervision probe failed; inspect retained stderr.'}
}finally{
 try{
  if($process){
   if(-not $process.HasExited){$process.Kill();$null=$process.WaitForExit(5000)}
   if($process.HasExited){
    [IO.File]::WriteAllText((Join-Path $root "Logs\guardian-supervisor-stderr-$id.txt"),$process.StandardError.ReadToEnd())
    [IO.File]::WriteAllText((Join-Path $root "Logs\guardian-supervisor-stdout-$id.txt"),$process.StandardOutput.ReadToEnd())
   }
  }
 }finally{Disable-LocalUser AgenticGuardian -ErrorAction Stop;$password.Dispose()}
}
if((Get-LocalUser AgenticGuardian).Enabled -or (Get-LocalUser AgenticPaperRuntime).Enabled){throw 'Disabled-account verification failed.'}
$result=Get-Content -LiteralPath $receipt -Raw | ConvertFrom-Json
if($result.schema_version -cne 'guardian-native-supervisor-fixture-v1' -or $result.probe_id -cne $id -or $result.guardian_process_identity_verified -ne $true -or $result.contained_child_identity_verified -ne $true -or @($result.cases).Count -ne 4 -or $result.execution_available -ne $false -or $result.reset_authorized -ne $false -or $result.trial_started -ne $false){throw 'Guardian supervisor scope failed.'}
if((Get-Item -LiteralPath (Join-Path $root "Logs\guardian-supervisor-stderr-$id.txt")).Length -ne 0){throw 'Guardian supervisor stderr is not empty.'}
if((Get-Content -LiteralPath (Join-Path $root "Logs\guardian-supervisor-stdout-$id.txt") -Raw).Trim() -cne 'GUARDIAN_NATIVE_SUPERVISION_COMPLETE_SYNTHETIC_ONLY'){throw 'Guardian supervisor stdout check failed.'}
& (Join-Path $PSScriptRoot 'audit_webull_guardian_release.ps1') -ExpectedManifestSha256 $pin | Out-Null
Assert-Probe
$summary=[ordered]@{probe_path=$probePath;command_line_characters=$commandLineCharacters;protected_probe_verified=$true;schema_version='guardian-supervisor-wrapper-v1';receipt_path=$receipt;receipt_sha256=(Get-FileHash -LiteralPath $receipt -Algorithm SHA256).Hash.ToLowerInvariant();probe_sha256=$probeHash;wrapper_sha256=(Get-FileHash -LiteralPath $PSCommandPath -Algorithm SHA256).Hash.ToLowerInvariant();manifest_sha256=$pin;guardian_disabled=$true;runtime_disabled=$true;execution_available=$false;reset_authorized=$false;trial_started=$false}
$summaryPath=Join-Path $root "Receipts\guardian-supervisor-wrapper-$id.json"
$stream=[IO.File]::Open($summaryPath,[IO.FileMode]::CreateNew,[IO.FileAccess]::Write)
try{$bytes=[Text.Encoding]::UTF8.GetBytes(($summary | ConvertTo-Json));$stream.Write($bytes,0,$bytes.Length);$stream.Flush($true)}finally{$stream.Dispose()}
Write-Output "Guardian native supervision fixture passed. Account disabled again. Evidence: $summaryPath"
Write-Output 'Synthetic processes only; real signed-reference/app/service lifecycle, passkey approval and reset remain unqualified.'
