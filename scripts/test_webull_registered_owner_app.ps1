# Accepted-credential app construction under actual standard owner; no challenge/listener/guardian.
[CmdletBinding()]
param()
$ErrorActionPreference='Stop'
$owner=[Security.Principal.WindowsIdentity]::GetCurrent()
if(-not [Environment]::Is64BitProcess -or -not ([Security.Principal.WindowsPrincipal]::new($owner)).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)){throw 'Elevated 64-bit owner required.'}
$guardian=Get-LocalUser AgenticGuardian
if($guardian.Enabled -or (Get-LocalUser AgenticPaperRuntime).Enabled){throw 'Both accounts must start disabled.'}
$pin='7bcd38f561458069c9e3e722edad8d72dfeecb0f591f18e00c45e772139d275d'
$audit=& (Join-Path $PSScriptRoot 'audit_webull_guardian_release.ps1') -ExpectedManifestSha256 $pin | ConvertFrom-Json
$python=Join-Path $audit.installed_directory 'python.exe'
$driver=Join-Path $audit.installed_directory 'app\scripts\webull_owner_auth_diagnostic.py'
$root='C:\ProgramData\AgenticInvestingGuardian'
$id=[guid]::NewGuid().ToString('N')
$admin=[Security.Principal.SecurityIdentifier]::new('S-1-5-32-544')
$system=[Security.Principal.SecurityIdentifier]::new('S-1-5-18')
function Rules($Acl){@($Acl.GetAccessRules($true,$true,[Security.Principal.SecurityIdentifier]) | ForEach-Object {'{0}|{1}|{2}|{3}|{4}|{5}' -f $_.IdentityReference.Value,[int]$_.FileSystemRights,[int]$_.InheritanceFlags,[int]$_.PropagationFlags,[int]$_.AccessControlType,$_.IsInherited} | Sort-Object)}
function Write-Protected([string]$Path,[byte[]]$Bytes){
 $stream=[IO.File]::Open($Path,[IO.FileMode]::CreateNew,[IO.FileAccess]::Write)
 try{$stream.Write($Bytes,0,$Bytes.Length);$stream.Flush($true)}finally{$stream.Dispose()}
 $acl=[Security.AccessControl.FileSecurity]::new();$acl.SetOwner($admin);$acl.SetAccessRuleProtection($true,$false)
 foreach($sid in @($admin,$system,$owner.User,$guardian.SID)){
  $rights=if($sid -eq $admin -or $sid -eq $system){'FullControl'}else{'ReadAndExecute'}
  $acl.AddAccessRule([Security.AccessControl.FileSystemAccessRule]::new($sid,$rights,'Allow'))
 }
 Set-Acl -LiteralPath $Path -AclObject $acl
 $actual=Get-Acl -LiteralPath $Path
 if(-not $actual.AreAccessRulesProtected -or $actual.GetOwner([Security.Principal.SecurityIdentifier]) -ne $admin -or (Compare-Object (Rules $acl) (Rules $actual)) -or ((Get-Item -LiteralPath $Path).Attributes -band [IO.FileAttributes]::ReparsePoint)){throw 'Protected fixture file check failed.'}
}
$materialStart=[Diagnostics.ProcessStartInfo]::new()
$materialStart.FileName=$python;$materialStart.Arguments='-I -B "'+$driver+'" material '+$owner.User.Value+' '+$guardian.SID.Value+' '+$pin

$enrollment='C:\Users\cesar\AppData\Local\AgenticInvesting\owner-passkey-enrollment.json'
$enrollmentPin='b16cd23aa4b03c324f3207e9df2b4ae927a300216ef0ad227543a36c60b4a4bf'
$materialStart.Arguments+=' "'+$enrollment+'" '+$enrollmentPin
$materialStart.UseShellExecute=$false;$materialStart.CreateNoWindow=$true;$materialStart.RedirectStandardError=$true;$materialStart.RedirectStandardOutput=$true
$materialProcess=[Diagnostics.Process]::Start($materialStart);$null=$materialProcess.Handle
$materialOutput=$materialProcess.StandardOutput.ReadToEndAsync();$materialError=$materialProcess.StandardError.ReadToEndAsync()
try{
 if(-not $materialProcess.WaitForExit(10000)){$materialProcess.Kill();throw 'Synthetic material preparation timeout.'}
 $materialProcess.WaitForExit()
 if($materialProcess.ExitCode -ne 0 -or $materialError.Result.Length -ne 0){throw 'Synthetic material preparation failed.'}
 $material=[Text.Encoding]::UTF8.GetString([Convert]::FromBase64String($materialOutput.Result.Trim())) | ConvertFrom-Json
}finally{$materialProcess.Dispose()}
if($material.real_public_credential_only -ne $true -or $material.purpose -cne 'OWNER_AUTH_DIAGNOSTIC_ONLY'){throw 'Authentication diagnostic scope required.'}
$configurationPath=Join-Path $root "Code\HostConfig-$id.json"
Write-Protected $configurationPath ([Text.Encoding]::UTF8.GetBytes(($material.configuration | ConvertTo-Json -Depth 20 -Compress)))
$configurationHash=(Get-FileHash -LiteralPath $configurationPath).Hash.ToLowerInvariant()
$layoutReceipt=@(& (Join-Path $PSScriptRoot 'prepare_webull_review_layout.ps1') -ConfigurationPath $configurationPath -ExpectedConfigurationSha256 $configurationHash -SyntheticOnly -ExpectedManifestSha256 $pin)
if($layoutReceipt.Count -ne 1){throw 'One layout receipt required.'}
$layout=Get-Content -LiteralPath $layoutReceipt[0] -Raw | ConvertFrom-Json
$ownerDirectory=Split-Path $layout.journal_path -Parent


$journalHash=(Get-FileHash -LiteralPath $layout.journal_path).Hash.ToLowerInvariant()
$registryPin='9fe4cf37ee9513eb9668dc2de0997b117abe83704ef0cc79a1c27e38b046b778'
$registry=Join-Path $root "Code\AcceptedOwnerCredential-$registryPin.json"
$resultPath=Join-Path $ownerDirectory 'registered-owner-app-result.json'
$bootstrap=Join-Path $root "Code\RegisteredOwnerBootstrap-$id.py"
$c=@{owner=$owner.User.Value;guardian=$guardian.SID.Value;manifest=$pin;configuration=$configurationPath;hash=$configurationHash;registry=$registry;registry_pin=$registryPin;result=$resultPath;stdout=(Join-Path $ownerDirectory 'owner-stdout.txt');stderr=(Join-Path $ownerDirectory 'owner-stderr.txt')} | ConvertTo-Json -Compress
$body=@'
import hashlib,json,os
from datetime import UTC,datetime
from pathlib import Path
from security.webull_pinned_owner_app import create_registered_owner_app
def unavailable(_):raise PermissionError('Construction only; no guardian transport')
app=create_registered_owner_app(c['configuration'],owner_sid=c['owner'],guardian_sid=c['guardian'],expected_sha256=c['hash'],expected_manifest_sha256=c['manifest'],registry_path=c['registry'],expected_registry_sha256=c['registry_pin'],expected_credential_sha256='fc0761142d56f020eac42868d377fb12849458e90a6db5c23edc9bc6ca58e22b',guardian_exchange=unavailable)
review=next(route.endpoint for route in app.routes if route.path=='/review')()
if review['reset_authorized'] is not False or review['execution_available'] is not False:raise ValueError('Review-only scope required')
result=dict(schema_version='registered-owner-app-construction-v1',observed_at_utc=datetime.now(UTC).isoformat(),configuration_sha256=c['hash'],registry_sha256=c['registry_pin'],manifest_sha256=c['manifest'],envelope_sha256=review['digest'],standard_owner_process_verified=True,registered_factory_constructed=True,protected_registry_verified=True,synthetic_account_and_plan_context_only=True,http_listener_started=False,challenge_issued=False,passkey_used=False,guardian_exchange_called=False,reset_authorized=False,execution_available=False,trial_started=False)
with Path(c['result']).open('x',encoding='utf-8') as stream:json.dump(result,stream);stream.flush();os.fsync(stream.fileno())
'@
$code=@('import sys',('c='+$c),"sys.stdout=open(c['stdout'],'x',encoding='utf-8')","sys.stderr=open(c['stderr'],'x',encoding='utf-8')",$body) -join [Environment]::NewLine
Write-Protected $bootstrap ([Text.Encoding]::UTF8.GetBytes($code))
& $python -I -B -c 'import pathlib,sys;compile(pathlib.Path(sys.argv[1]).read_bytes(),sys.argv[1],sys.argv[2])' $bootstrap exec
if($LASTEXITCODE -ne 0){throw 'Registered bootstrap compilation failed.'}
. (Join-Path $PSScriptRoot 'webull_standard_owner_process.ps1')
$launcher=New-StandardOwnerLauncher
$variables=@{SystemRoot=$env:WINDIR;WINDIR=$env:WINDIR;PATH=(Join-Path $env:WINDIR 'System32');TEMP=$ownerDirectory;TMP=$ownerDirectory}
$environment=(@($variables.Keys | Sort-Object | ForEach-Object {$_+'='+$variables[$_]}) -join [char]0)+[char]0+[char]0
$ownerExit=$launcher::Run($python,('"'+$python+'" -I -B "'+$bootstrap+'"'),$environment,$ownerDirectory)
if($ownerExit -ne 0){throw "Registered owner construction failed; retain diagnostics: $ownerDirectory\owner-stderr.txt"}
$result=Get-Content -LiteralPath $resultPath -Raw | ConvertFrom-Json
foreach($flag in @('standard_owner_process_verified','registered_factory_constructed','protected_registry_verified','synthetic_account_and_plan_context_only')){if($result.$flag -isnot [bool] -or $result.$flag -ne $true){throw 'Registered construction evidence mismatch.'}}
foreach($flag in @('http_listener_started','challenge_issued','passkey_used','guardian_exchange_called','reset_authorized','execution_available','trial_started')){if($result.$flag -isnot [bool] -or $result.$flag -ne $false){throw 'Construction scope mismatch.'}}
if($result.configuration_sha256 -cne $configurationHash -or $result.registry_sha256 -cne $registryPin -or $result.manifest_sha256 -cne $pin){throw 'Result pins mismatch.'}
foreach($log in @('owner-stdout.txt','owner-stderr.txt')){if((Get-Item -LiteralPath (Join-Path $ownerDirectory $log)).Length -ne 0){throw 'Nonempty construction diagnostics.'}}
if((Get-FileHash -LiteralPath $layout.journal_path).Hash.ToLowerInvariant() -cne $journalHash -or @(Get-ChildItem -LiteralPath $material.configuration.reference_directory -Force).Count -ne 0 -or (Get-LocalUser AgenticGuardian).Enabled -or (Get-LocalUser AgenticPaperRuntime).Enabled){throw 'State/account changes observed.'}
$null=& (Join-Path $PSScriptRoot 'audit_webull_guardian_release.ps1') -ExpectedManifestSha256 $pin
$links=[ordered]@{}
foreach($path in @($PSCommandPath,$configurationPath,$bootstrap,$layoutReceipt[0],$resultPath,$layout.journal_path,$registry,(Join-Path $PSScriptRoot 'webull_standard_owner_process.ps1'))){$links[$path]=(Get-FileHash -LiteralPath $path).Hash.ToLowerInvariant()}
$wrapper=Join-Path $root "Receipts\registered-owner-app-wrapper-$id.json"
$value=[ordered]@{schema_version='registered-owner-app-wrapper-v1';fixture_id=$id;manifest_sha256=$pin;configuration_path=$configurationPath;result_path=$resultPath;journal_bytes_unchanged=$true;retained_hash_links=$links;guardian_disabled=$true;runtime_disabled=$true;synthetic_account_and_plan_context_only=$true;http_listener_started=$false;challenge_issued=$false;guardian_started=$false;passkey_used=$false;reset_authorized=$false;execution_available=$false;trial_started=$false}
$stream=[IO.File]::Open($wrapper,[IO.FileMode]::CreateNew,[IO.FileAccess]::Write)
try{$bytes=[Text.Encoding]::UTF8.GetBytes(($value | ConvertTo-Json -Depth 8));$stream.Write($bytes,0,$bytes.Length);$stream.Flush($true)}finally{$stream.Dispose()}
Write-Output "Registered owner app construction passed under actual standard-owner token. Evidence: $wrapper"
Write-Output 'No listener, challenge, passkey or guardian; both accounts disabled. Account/plan context remains synthetic; reset and trading unavailable.'
