# Actual standard-owner pinned app construction; no listener, challenge, guardian launch or broker.
[CmdletBinding()]
param([switch]$PrepareOnly)
$ErrorActionPreference='Stop'
$owner=[Security.Principal.WindowsIdentity]::GetCurrent()
if(-not [Environment]::Is64BitProcess -or -not ([Security.Principal.WindowsPrincipal]::new($owner)).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)){throw 'Elevated 64-bit owner required.'}
$guardian=Get-LocalUser AgenticGuardian
if($guardian.Enabled -or (Get-LocalUser AgenticPaperRuntime).Enabled){throw 'Both accounts must start disabled.'}
$pin='ceaece1e23febc153bdb8d1a3db2e575db3471397713cb027e23e8fd736f8fc7'
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
$bootstrap=Join-Path $root "Code\OwnerCredentialBindingBootstrap-$id.py"
$c=@{driver=$driver;owner=$owner.User.Value;guardian=$guardian.SID.Value;manifest=$pin;configuration=$configurationPath;hash=$configurationHash;stdout=(Join-Path $ownerDirectory 'owner-stdout.txt');stderr=(Join-Path $ownerDirectory 'owner-stderr.txt')} | ConvertTo-Json -Compress
$code=@('import runpy,sys',('c='+$c),"sys.stdout=open(c['stdout'],'x',encoding='utf-8')","sys.stderr=open(c['stderr'],'x',encoding='utf-8')","sys.argv=[c['driver'],'bind',c['configuration'],c['hash'],c['manifest'],c['owner'],c['guardian']]","runpy.run_path(c['driver'],run_name='__main__')") -join [Environment]::NewLine
Write-Protected $bootstrap ([Text.Encoding]::UTF8.GetBytes($code))
if($PrepareOnly){
 [ordered]@{schema_version='owner-credential-binding-preparation-v1';purpose='OWNER_REVIEW_CREDENTIAL_BINDING_ONLY';configuration_path=$configurationPath;configuration_sha256=$configurationHash;bootstrap_path=$bootstrap;bootstrap_sha256=(Get-FileHash -LiteralPath $bootstrap).Hash.ToLowerInvariant();layout_receipt_path=$layoutReceipt[0];public_enrollment_sha256=$enrollmentPin;manifest_sha256=$pin;guardian_disabled=$true;runtime_disabled=$true;listener_started=$false;passkey_used=$false;trial_started=$false} | ConvertTo-Json
 return
}
. (Join-Path $PSScriptRoot 'webull_standard_owner_process.ps1')
$launcher=New-StandardOwnerLauncher
Write-Host 'Open http://localhost:8769 yourself now. Once it loads, select Bind this credential with Windows Hello / passkey.'
Write-Host 'The binding page closes after 40 seconds. Binding this credential does not approve a review, reset or trading. No guardian password is needed.'
$variables=@{SystemRoot=$env:WINDIR;WINDIR=$env:WINDIR;PATH=(Join-Path $env:WINDIR 'System32');TEMP=$ownerDirectory;TMP=$ownerDirectory}
$environment=(@($variables.Keys | Sort-Object | ForEach-Object {$_+'='+$variables[$_]}) -join [char]0)+[char]0+[char]0
$ownerExit=$launcher::Run($python,('"'+$python+'" -I -B "'+$bootstrap+'"'),$environment,$ownerDirectory)
if($ownerExit -ne 0){throw "Owner credential binding failed/expired; retain context and diagnostics: $ownerDirectory\owner-stderr.txt"}
$resultPath=Join-Path $ownerDirectory 'owner-credential-binding.json'
$terminalPath=Join-Path $ownerDirectory 'owner-credential-binding-terminal.json'
$result=Get-Content -LiteralPath $resultPath -Raw | ConvertFrom-Json
$terminal=Get-Content -LiteralPath $terminalPath -Raw | ConvertFrom-Json
if($result.purpose -cne 'OWNER_REVIEW_CREDENTIAL_BINDING_ONLY' -or $result.authentication_verified -ne $true -or $result.credential_binding_authorized -ne $true -or $result.standard_owner_process_verified -ne $true -or $result.configuration_sha256 -cne $configurationHash -or $terminal.http_listener_closed -ne $true){throw 'Diagnostic result mismatch.'}
foreach($name in @('review_signature_issued','guardian_called','reset_authorized','execution_available','trial_started')){if($result.$name -isnot [bool] -or $result.$name -ne $false){throw 'Authentication scope mismatch.'}}
foreach($log in @('owner-stdout.txt','owner-stderr.txt')){if((Get-Item -LiteralPath (Join-Path $ownerDirectory $log)).Length -ne 0){throw 'Nonempty authentication diagnostics.'}}
if((Get-FileHash -LiteralPath $layout.journal_path).Hash.ToLowerInvariant() -ne $journalHash -or @(Get-ChildItem -LiteralPath $material.configuration.reference_directory -Force).Count -ne 0 -or (Get-LocalUser AgenticGuardian).Enabled -or (Get-LocalUser AgenticPaperRuntime).Enabled){throw 'Unexpected review state/account change.'}
$null=& (Join-Path $PSScriptRoot 'audit_webull_guardian_release.ps1') -ExpectedManifestSha256 $pin
$links=[ordered]@{}
foreach($path in @($PSCommandPath,$configurationPath,$bootstrap,$layoutReceipt[0],$resultPath,$terminalPath,$layout.journal_path,$enrollment,(Join-Path $PSScriptRoot 'webull_standard_owner_process.ps1'))){$links[$path]=(Get-FileHash -LiteralPath $path).Hash.ToLowerInvariant()}
$wrapper=Join-Path $root "Receipts\owner-credential-binding-wrapper-$id.json"
$value=[ordered]@{schema_version='owner-credential-binding-wrapper-v1';fixture_id=$id;purpose='OWNER_REVIEW_CREDENTIAL_BINDING_ONLY';manifest_sha256=$pin;configuration_path=$configurationPath;result_path=$resultPath;terminal_path=$terminalPath;journal_bytes_unchanged=$true;retained_hash_links=$links;guardian_disabled=$true;runtime_disabled=$true;credential_binding_authorized=$true;guardian_started=$false;review_signature_issued=$false;reset_authorized=$false;execution_available=$false;trial_started=$false}
$stream=[IO.File]::Open($wrapper,[IO.FileMode]::CreateNew,[IO.FileAccess]::Write)
try{$bytes=[Text.Encoding]::UTF8.GetBytes(($value | ConvertTo-Json -Depth 8));$stream.Write($bytes,0,$bytes.Length);$stream.Flush($true)}finally{$stream.Dispose()}
Write-Output "Owner review credential-binding ceremony passed. Accounts remain disabled. Evidence: $wrapper"
Write-Output 'Credential-binding evidence only; protected registry installation, real review/app/guardian lifecycle, reset and trading remain unqualified.'
