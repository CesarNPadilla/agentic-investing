# Disposable synthetic layout only. Never provisions a real approval or starts a host.
[CmdletBinding()]
param(
 [Parameter(Mandatory=$true)][string]$ConfigurationPath,
 [Parameter(Mandatory=$true)][ValidatePattern('^[0-9a-f]{64}$')][string]$ExpectedConfigurationSha256,
 [Parameter(Mandatory=$true)][switch]$SyntheticOnly,
 [ValidatePattern('^[0-9a-f]{64}$')][string]$ExpectedManifestSha256='c46afdaf67cb70f437507f5975791c5fb461a3cfdf1774a72b4c9ae573774c41'
)
$ErrorActionPreference='Stop'
if(-not $SyntheticOnly){throw 'Only synthetic qualification is supported.'}
$owner=[Security.Principal.WindowsIdentity]::GetCurrent()
if(-not [Environment]::Is64BitProcess -or -not ([Security.Principal.WindowsPrincipal]::new($owner)).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)){throw 'Elevated 64-bit owner required.'}
$guardian=Get-LocalUser AgenticGuardian
if($guardian.Enabled -or (Get-LocalUser AgenticPaperRuntime).Enabled){throw 'Both accounts must remain disabled.'}
$manifest=$ExpectedManifestSha256
$audit=& (Join-Path $PSScriptRoot 'audit_webull_guardian_release.ps1') -ExpectedManifestSha256 $manifest | ConvertFrom-Json
$python=Join-Path $audit.installed_directory 'python.exe'
$code=@'
import json,sys
from datetime import UTC,datetime
from security.windows_protected_config import ProtectedConfigReader
from security.webull_guardian_host_config import parse_pinned_host_config
path,pin,owner,guardian,manifest=sys.argv[1:6]
raw=ProtectedConfigReader().read(path,owner_sid=owner,guardian_sid=guardian)
config=parse_pinned_host_config(raw,expected_sha256=pin,expected_manifest_sha256=manifest,now=datetime.now(UTC))
if config.owner_sid!=owner or config.guardian_sid!=guardian:raise ValueError('Role binding mismatch')
if config.envelope.action=='REVIEW_DISPOSABLE_CONTROLS_TEST_ONLY':
 from scripts.webull_disposable_controls_ceremony import controls_only
 controls_only(config)
elif config.envelope.account_binding_sha256!='a'*64 or config.envelope.reset_review_sha256!='b'*64:raise ValueError('Synthetic context required')
print(json.dumps(dict(reference=config.reference_directory,journal=config.journal_path,context_sha256=config.envelope.digest())))
'@
function Run-EngineeringPython([string]$Code,[string]$Arguments){
 $encoded=[Convert]::ToBase64String([Text.Encoding]::UTF8.GetBytes($Code))
 $start=[Diagnostics.ProcessStartInfo]::new()
 $start.FileName=$python;$start.Arguments='-I -B -c "import base64;exec(base64.b64decode('''+$encoded+'''))" '+$Arguments
 $start.UseShellExecute=$false;$start.CreateNoWindow=$true;$start.RedirectStandardOutput=$true;$start.RedirectStandardError=$true
 $process=[Diagnostics.Process]::Start($start);$null=$process.Handle
 try{
  if(-not $process.WaitForExit(10000)){$process.Kill();throw 'Synthetic layout operation exceeded deadline.'}
  $process.WaitForExit()
  $output=$process.StandardOutput.ReadToEnd();$errorText=$process.StandardError.ReadToEnd()
  if($process.ExitCode -ne 0 -or $errorText.Length -ne 0){throw 'Synthetic layout validation/initialization failed; partial files retained.'}
  return $output
 }finally{$process.Dispose()}
}
$arguments='"'+$ConfigurationPath+'" '+$ExpectedConfigurationSha256+' '+$owner.User.Value+' '+$guardian.SID.Value+' '+$manifest
$paths=(Run-EngineeringPython $code $arguments) | ConvertFrom-Json
$journalDirectory=Split-Path $paths.journal -Parent
$admin=[Security.Principal.SecurityIdentifier]::new('S-1-5-32-544')
$system=[Security.Principal.SecurityIdentifier]::new('S-1-5-18')
function Rules($Acl){@($Acl.GetAccessRules($true,$true,[Security.Principal.SecurityIdentifier]) | ForEach-Object {'{0}|{1}|{2}|{3}|{4}|{5}' -f $_.IdentityReference.Value,[int]$_.FileSystemRights,[int]$_.InheritanceFlags,[int]$_.PropagationFlags,[int]$_.AccessControlType,$_.IsInherited} | Sort-Object)}
function Protect-Layout([string]$Path,[bool]$Directory,[string]$Writer){
 if($Directory){$acl=[Security.AccessControl.DirectorySecurity]::new()}else{$acl=[Security.AccessControl.FileSecurity]::new()}
 $acl.SetOwner($admin);$acl.SetAccessRuleProtection($true,$false)
 foreach($sid in @($admin,$system,$owner.User,$guardian.SID)){
  $rights=if($sid -eq $admin -or $sid -eq $system){'FullControl'}elseif(($Writer -ceq 'guardian' -and $sid -eq $guardian.SID) -or ($Writer -ceq 'owner' -and $sid -eq $owner.User)){'Modify'}else{'ReadAndExecute'}
  $inherit=if($Directory){'ContainerInherit,ObjectInherit'}else{'None'}
  $acl.AddAccessRule([Security.AccessControl.FileSystemAccessRule]::new($sid,$rights,$inherit,'None','Allow'))
 }
 Set-Acl -LiteralPath $Path -AclObject $acl
 $actual=Get-Acl -LiteralPath $Path
 if(-not $actual.AreAccessRulesProtected -or $actual.GetOwner([Security.Principal.SecurityIdentifier]) -ne $admin -or (Compare-Object (Rules $acl) (Rules $actual))){throw 'Exact synthetic layout ACL mismatch.'}
}
foreach($path in @($paths.reference,$journalDirectory)){
 if(Test-Path -LiteralPath $path){throw 'Fresh layout required; retain prior evidence and do not reuse.'}
 $ancestor=Split-Path $path -Parent
 while($ancestor){
  if((Get-Item -LiteralPath $ancestor -Force).Attributes -band [IO.FileAttributes]::ReparsePoint){throw 'Ordinary layout ancestry required.'}
  $next=Split-Path $ancestor -Parent
  if($next -eq $ancestor){break}
  $ancestor=$next
 }
}
New-Item -ItemType Directory -Path $paths.reference | Out-Null
Protect-Layout $paths.reference $true 'guardian'
New-Item -ItemType Directory -Path $journalDirectory | Out-Null
Protect-Layout $journalDirectory $true 'owner'
$initialize=@'
import json,sys
from datetime import UTC,datetime
from security.windows_protected_config import ProtectedConfigReader
from security.webull_guardian_host_config import parse_pinned_host_config
from security.webull_review_journal import ReviewJournal
path,pin,owner,guardian,manifest=sys.argv[1:6]
raw=ProtectedConfigReader().read(path,owner_sid=owner,guardian_sid=guardian)
config=parse_pinned_host_config(raw,expected_sha256=pin,expected_manifest_sha256=manifest,now=datetime.now(UTC))
ReviewJournal.initialize(config.journal_path,expected_envelope=config.envelope)
print('SYNTHETIC_EMPTY_JOURNAL_INITIALIZED')
'@
if((Run-EngineeringPython $initialize $arguments).Trim() -cne 'SYNTHETIC_EMPTY_JOURNAL_INITIALIZED'){throw 'Journal initialization confirmation missing.'}
Protect-Layout $paths.journal $false 'owner'
if(@(Get-ChildItem -LiteralPath $paths.reference -Force).Count -ne 0 -or @(Get-ChildItem -LiteralPath $journalDirectory -Force).Count -ne 1){throw 'Unexpected synthetic layout contents.'}
if($guardian.Enabled -or (Get-LocalUser AgenticGuardian).Enabled -or (Get-LocalUser AgenticPaperRuntime).Enabled){throw 'Disabled identities required.'}
$record=[ordered]@{schema_version='webull-synthetic-review-layout-v1';configuration_path=$ConfigurationPath;configuration_sha256=$ExpectedConfigurationSha256;reference_directory=$paths.reference;journal_path=$paths.journal;journal_sha256=(Get-FileHash -LiteralPath $paths.journal).Hash.ToLowerInvariant();context_sha256=$paths.context_sha256;exact_protected_objects_verified=3;reference_writer='GUARDIAN';journal_writer='OWNER';guardian_disabled=$true;runtime_disabled=$true;synthetic_only=$true;real_approval_provisioned=$false;host_started=$false;service_deployed=$false;reset_authorized=$false;execution_available=$false;trial_started=$false}
$receipt=Join-Path 'C:\ProgramData\AgenticInvestingGuardian\Receipts' ('layout-preparation-'+[guid]::NewGuid().ToString('N')+'.json')
$stream=[IO.File]::Open($receipt,[IO.FileMode]::CreateNew,[IO.FileAccess]::Write)
try{$bytes=[Text.Encoding]::UTF8.GetBytes(($record | ConvertTo-Json));$stream.Write($bytes,0,$bytes.Length);$stream.Flush($true)}finally{$stream.Dispose()}
Write-Output $receipt
