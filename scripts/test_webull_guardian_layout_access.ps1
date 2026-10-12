# Actual guardian-token synthetic journal/reference access; no signed host, reset or broker.
[CmdletBinding()]
param([switch]$PrepareOnly)
$ErrorActionPreference='Stop'
$owner=[Security.Principal.WindowsIdentity]::GetCurrent()
if(-not [Environment]::Is64BitProcess -or -not ([Security.Principal.WindowsPrincipal]::new($owner)).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)){throw 'Elevated 64-bit owner PowerShell required.'}
$guardian=Get-LocalUser AgenticGuardian
if($guardian.Enabled -or (Get-LocalUser AgenticPaperRuntime).Enabled){throw 'Both accounts must start disabled.'}
$pin='c46afdaf67cb70f437507f5975791c5fb461a3cfdf1774a72b4c9ae573774c41'
$audit=& (Join-Path $PSScriptRoot 'audit_webull_guardian_release.ps1') -ExpectedManifestSha256 $pin | ConvertFrom-Json
$root='C:\ProgramData\AgenticInvestingGuardian'
$id=[guid]::NewGuid().ToString('N')
$receipt=Join-Path $root "Receipts\guardian-layout-access-$id.json"
$probe=@'
import json,os,sys
from datetime import UTC,datetime
from pathlib import Path
from fido2.webauthn import AttestedCredentialData
from security.windows_protected_config import load_guardian_config
from security.webull_review_journal import ReviewJournal
from security.webull_guardian_reference import GuardianReference
guardian,owner,path,pin,identifier=sys.argv[1:6]
manifest='c46afdaf67cb70f437507f5975791c5fb461a3cfdf1774a72b4c9ae573774c41'
config=load_guardian_config(path,owner_sid=owner,guardian_sid=guardian,expected_sha256=pin,expected_manifest_sha256=manifest,now=datetime.now(UTC))
journal=ReviewJournal(config.journal_path,expected_envelope=config.envelope)
reference=GuardianReference(config.reference_directory,journal,AttestedCredentialData(bytes.fromhex(config.public_credential_hex)))
if reference._rows():raise ValueError('Empty synthetic journal required')
try:
 with journal.path.open('r+b'):pass
except PermissionError:pass
else:raise PermissionError('Guardian journal write unexpectedly allowed')
marker=reference.directory/('synthetic-access-'+identifier+'.json')
reference._exclusive(marker,{'schema_version':'synthetic-guardian-layout-access-v1','reset_authorized':False,'execution_available':False,'trial_started':False})
record={'schema_version':'guardian-layout-access-fixture-v1','probe_id':identifier,'observed_at_utc':datetime.now(UTC).isoformat(),'guardian_process_identity_verified':True,'protected_configuration_loaded':True,'configuration_sha256':pin,'synthetic_public_credential_only':True,'journal_read_verified':True,'guardian_journal_write_denied':True,'reference_marker_path':str(marker),'reference_write_verified':True,'real_reference_used':False,'service_deployed':False,'execution_available':False,'reset_authorized':False,'trial_started':False}
root=Path(r'C:\ProgramData\AgenticInvestingGuardian')
with (root/'Receipts'/('guardian-layout-access-'+identifier+'.json')).open('x',encoding='utf-8') as stream:
 json.dump(record,stream);stream.flush();os.fsync(stream.fileno())
print('GUARDIAN_LAYOUT_ACCESS_COMPLETE_SYNTHETIC_ONLY')
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
$probePath=Join-Path $codeParent "guardian-layout-access-$id.py"
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
$builder=@'
import base64,hashlib,json,sys
from datetime import UTC,datetime,timedelta
from uuid import uuid4
from cryptography.hazmat.primitives.asymmetric import ec
from fido2.cose import ES256
from fido2.webauthn import AttestedCredentialData
from security.webull_guardian_host_config import GuardianHostConfig
from security.webull_review_signature import ReviewEnvelope
owner,guardian=sys.argv[1:3]
credential=AttestedCredentialData.create(bytes(16),b'synthetic-loader-only',ES256.from_cryptography_key(ec.generate_private_key(ec.SECP256R1()).public_key()))
now=datetime.now(UTC);identifier=str(uuid4())
envelope=ReviewEnvelope(schema_version='webull-reset-prerequisite-review-v1',action='REVIEW_WEBULL_RESET_PRECONDITIONS_ONLY',review_id=uuid4(),account_binding_sha256='a'*64,reset_review_sha256='b'*64,credential_sha256=hashlib.sha256(bytes(credential)).hexdigest(),issued_at=now,expires_at=now+timedelta(seconds=300))
value=dict(schema_version='webull-guardian-host-config-v1',provisioning_id=identifier,guardian_sid=guardian,owner_sid=owner,installed_manifest_sha256='c46afdaf67cb70f437507f5975791c5fb461a3cfdf1774a72b4c9ae573774c41',envelope=envelope.model_dump(mode='json'),public_credential_hex=bytes(credential).hex(),reference_directory=r'C:\ProgramData\AgenticInvestingGuardian\References\Review-'+identifier,journal_path=r'C:\ProgramData\AgenticInvestingPaper\OwnerControl\Review-'+identifier+r'\review.sqlite',process_deadline_seconds=15,reset_authorized=False,execution_available=False,trial_started=False)
raw=json.dumps(value).encode();GuardianHostConfig.model_validate_json(raw)
print(base64.b64encode(raw).decode())
'@
$encodedBuilder=[Convert]::ToBase64String([Text.Encoding]::UTF8.GetBytes($builder))
$buildStart=[Diagnostics.ProcessStartInfo]::new()
$buildStart.FileName=$executable
$buildStart.Arguments='-I -B -c "import base64;exec(base64.b64decode('''+$encodedBuilder+'''))" '+$owner.User.Value+' '+$guardian.SID.Value
$buildStart.UseShellExecute=$false;$buildStart.CreateNoWindow=$true;$buildStart.RedirectStandardError=$true;$buildStart.RedirectStandardOutput=$true
$buildProcess=[Diagnostics.Process]::Start($buildStart);$null=$buildProcess.Handle
try{
 if(-not $buildProcess.WaitForExit(10000)){$buildProcess.Kill();throw 'Synthetic builder timeout.'}
 $buildProcess.WaitForExit();$encodedConfiguration=$buildProcess.StandardOutput.ReadToEnd().Trim();$buildError=$buildProcess.StandardError.ReadToEnd()
 if($buildProcess.ExitCode -ne 0 -or $buildError.Length -ne 0 -or $encodedConfiguration -cnotmatch '^[A-Za-z0-9+/]+={0,2}$'){throw 'Synthetic configuration builder failed.'}
}finally{$buildProcess.Dispose()}
$configBytes=[Convert]::FromBase64String($encodedConfiguration)
$configPath=Join-Path $codeParent "HostConfig-$id.json"
$stream=[IO.File]::Open($configPath,[IO.FileMode]::CreateNew,[IO.FileAccess]::Write)
try{$stream.Write($configBytes,0,$configBytes.Length);$stream.Flush($true)}finally{$stream.Dispose()}
Set-Acl -LiteralPath $configPath -AclObject $probeAcl
$configHash=(Get-FileHash -LiteralPath $configPath -Algorithm SHA256).Hash.ToLowerInvariant()
$configAcl=Get-Acl -LiteralPath $configPath
if(-not $configAcl.AreAccessRulesProtected -or $configAcl.GetOwner([Security.Principal.SecurityIdentifier]) -ne $admin -or (Compare-Object (Probe-Rules $probeAcl) (Probe-Rules $configAcl))){throw 'Protected synthetic configuration ACL mismatch.'}
$arguments='-I -B "'+$probePath+'" '+$guardian.SID.Value+' '+$owner.User.Value+' "'+$configPath+'" '+$configHash+' '+$id
$commandLineCharacters=$executable.Length+3+$arguments.Length
if($commandLineCharacters -ge 1024){throw 'Credentialed command line exceeds safe bound.'}
$layoutReceipt=@(& (Join-Path $PSScriptRoot 'prepare_webull_review_layout.ps1') -ConfigurationPath $configPath -ExpectedConfigurationSha256 $configHash -SyntheticOnly)
if($layoutReceipt.Count -ne 1 -or -not (Test-Path -LiteralPath $layoutReceipt[0])){throw 'Synthetic layout receipt missing.'}
$layoutReceiptPath=$layoutReceipt[0]
if($PrepareOnly){
 [ordered]@{schema_version='guardian-layout-access-source-preparation-v1';probe_path=$probePath;probe_sha256=$probeHash;configuration_path=$configPath;configuration_sha256=$configHash;engineering_builder_executed=$true;layout_receipt_path=$layoutReceiptPath;command_line_characters=$commandLineCharacters;protected_probe_verified=$true;probe_compilation_verified=$true;guardian_disabled=$true;runtime_disabled=$true;credential_prompted=$false;process_probe_started=$false} | ConvertTo-Json
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
    [IO.File]::WriteAllText((Join-Path $root "Logs\guardian-layout-access-stderr-$id.txt"),$process.StandardError.ReadToEnd())
    [IO.File]::WriteAllText((Join-Path $root "Logs\guardian-layout-access-stdout-$id.txt"),$process.StandardOutput.ReadToEnd())
   }
  }
 }finally{Disable-LocalUser AgenticGuardian -ErrorAction Stop;$password.Dispose()}
}
if((Get-LocalUser AgenticGuardian).Enabled -or (Get-LocalUser AgenticPaperRuntime).Enabled){throw 'Disabled-account verification failed.'}
$result=Get-Content -LiteralPath $receipt -Raw | ConvertFrom-Json
if($result.schema_version -cne 'guardian-layout-access-fixture-v1' -or $result.probe_id -cne $id -or $result.guardian_process_identity_verified -ne $true -or $result.protected_configuration_loaded -ne $true -or $result.configuration_sha256 -cne $configHash -or $result.synthetic_public_credential_only -ne $true -or $result.journal_read_verified -ne $true -or $result.guardian_journal_write_denied -ne $true -or $result.reference_write_verified -ne $true -or $result.execution_available -ne $false -or $result.reset_authorized -ne $false -or $result.trial_started -ne $false){throw 'Guardian supervisor scope failed.'}
if((Get-Item -LiteralPath (Join-Path $root "Logs\guardian-layout-access-stderr-$id.txt")).Length -ne 0){throw 'Guardian supervisor stderr is not empty.'}
if((Get-Content -LiteralPath (Join-Path $root "Logs\guardian-layout-access-stdout-$id.txt") -Raw).Trim() -cne 'GUARDIAN_LAYOUT_ACCESS_COMPLETE_SYNTHETIC_ONLY'){throw 'Guardian supervisor stdout check failed.'}
$retainedLayout=Get-Content -LiteralPath $layoutReceiptPath -Raw | ConvertFrom-Json
if((Get-FileHash -LiteralPath $retainedLayout.journal_path).Hash.ToLowerInvariant() -cne $retainedLayout.journal_sha256){throw 'Synthetic journal bytes changed during guardian access.'}
$expectedMarker=Join-Path $retainedLayout.reference_directory ("synthetic-access-$id.json")
if($result.reference_marker_path -cne $expectedMarker -or ((Get-Item -LiteralPath $expectedMarker).Attributes -band [IO.FileAttributes]::ReparsePoint)){throw 'Retained synthetic marker path rejected.'}
$marker=Get-Content -LiteralPath $expectedMarker -Raw | ConvertFrom-Json
if($marker.schema_version -cne 'synthetic-guardian-layout-access-v1' -or $marker.reset_authorized -ne $false -or $marker.execution_available -ne $false -or $marker.trial_started -ne $false){throw 'Synthetic marker scope rejected.'}
& (Join-Path $PSScriptRoot 'audit_webull_guardian_release.ps1') -ExpectedManifestSha256 $pin | Out-Null
Assert-Probe
$summary=[ordered]@{reference_marker_sha256=(Get-FileHash -LiteralPath $expectedMarker).Hash.ToLowerInvariant();journal_sha256=$retainedLayout.journal_sha256;layout_preparation_script_sha256=(Get-FileHash -LiteralPath (Join-Path $PSScriptRoot 'prepare_webull_review_layout.ps1')).Hash.ToLowerInvariant();layout_receipt_path=$layoutReceiptPath;layout_receipt_sha256=(Get-FileHash -LiteralPath $layoutReceiptPath).Hash.ToLowerInvariant();configuration_path=$configPath;configuration_sha256=$configHash;probe_path=$probePath;command_line_characters=$commandLineCharacters;protected_probe_verified=$true;schema_version='guardian-layout-access-wrapper-v1';receipt_path=$receipt;receipt_sha256=(Get-FileHash -LiteralPath $receipt -Algorithm SHA256).Hash.ToLowerInvariant();probe_sha256=$probeHash;wrapper_sha256=(Get-FileHash -LiteralPath $PSCommandPath -Algorithm SHA256).Hash.ToLowerInvariant();manifest_sha256=$pin;guardian_disabled=$true;runtime_disabled=$true;execution_available=$false;reset_authorized=$false;trial_started=$false}
$summaryPath=Join-Path $root "Receipts\guardian-layout-access-wrapper-$id.json"
$stream=[IO.File]::Open($summaryPath,[IO.FileMode]::CreateNew,[IO.FileAccess]::Write)
try{$bytes=[Text.Encoding]::UTF8.GetBytes(($summary | ConvertTo-Json));$stream.Write($bytes,0,$bytes.Length);$stream.Flush($true)}finally{$stream.Dispose()}
Write-Output "Guardian synthetic layout access fixture passed. Account disabled again. Evidence: $summaryPath"
Write-Output 'Synthetic public credential and configuration only; real signed-reference/app/service lifecycle, passkey approval and reset remain unqualified.'
