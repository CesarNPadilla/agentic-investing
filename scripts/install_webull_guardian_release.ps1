# New-directory pinned guardian code/environment installation. Starts nothing.
[CmdletBinding()]
param([Parameter(Mandatory=$true)][string]$SourceBundle,
 [Parameter(Mandatory=$true)][ValidatePattern('^[0-9a-f]{64}$')][string]$ExpectedManifestSha256,
 [switch]$ValidateOnly)
$ErrorActionPreference='Stop'
function Ordinary([string]$Path){if((Get-Item -LiteralPath $Path -Force).Attributes -band [IO.FileAttributes]::ReparsePoint){throw 'Reparse point forbidden.'}}
function Verify-Bundle([string]$Root){
 Ordinary $Root
 $manifestPath=Join-Path $Root 'guardian-release.json';Ordinary $manifestPath
 if((Get-FileHash $manifestPath -Algorithm SHA256).Hash.ToLowerInvariant() -cne $ExpectedManifestSha256){throw 'Guardian manifest digest mismatch.'}
 $manifest=Get-Content $manifestPath -Raw | ConvertFrom-Json
 if($manifest.schema_version -cnotin @('webull-guardian-release-v1','webull-guardian-release-v2','webull-guardian-release-v3','webull-guardian-release-v4','webull-guardian-release-v5','webull-guardian-release-v6','webull-guardian-release-v7','webull-guardian-release-v8','webull-guardian-release-v9','webull-guardian-release-v10','webull-guardian-release-v11') -or $manifest.scope -cne 'GUARDIAN_REVIEW_AND_SYNTHETIC_PIPE_ONLY_NO_SERVICE_NO_BROKER' -or $manifest.execution_available -isnot [bool] -or $manifest.execution_available -or $manifest.base_environment_manifest_sha256 -cne 'f2eb1b3b90ce7a79346ab72189ced4f59eda14ac9c89ddccda2139cc74cbd33b'){throw 'Guardian release scope mismatch.'}
 $names=@($manifest.files.PSObject.Properties.Name | Sort-Object)
 $expectedCount=switch -CaseSensitive ($manifest.schema_version){'webull-guardian-release-v11'{706};'webull-guardian-release-v10'{705};'webull-guardian-release-v9'{705};'webull-guardian-release-v8'{704};'webull-guardian-release-v7'{704};'webull-guardian-release-v6'{702};'webull-guardian-release-v5'{697};'webull-guardian-release-v4'{694};'webull-guardian-release-v3'{692};'webull-guardian-release-v2'{689};'webull-guardian-release-v1'{687}}
 if($names.Count -ne $expectedCount){throw 'Unexpected guardian inventory.'}
 $expectedSources=@(
  'app/security/webull_review_signature.py','app/security/webull_review_journal.py',
  'app/security/webull_guardian_reference.py','app/security/webull_guardian_bridge.py',
  'app/security/windows_guardian_request_pipe.py','app/security/windows_local_request_pipe.py',
  'app/security/windows_pipe_identity.py','app/security/webull_pipe_registration.py',
  'app/scripts/probe_webull_guardian_pipe.py'
 )
 if($manifest.schema_version -cin @('webull-guardian-release-v2','webull-guardian-release-v3','webull-guardian-release-v4','webull-guardian-release-v5','webull-guardian-release-v6','webull-guardian-release-v7','webull-guardian-release-v8','webull-guardian-release-v9','webull-guardian-release-v10','webull-guardian-release-v11')){
  $expectedSources+=@('app/security/windows_guardian_exchange_pipe.py','app/security/webull_guardian_recovery_inspection.py')
 }
 if($manifest.schema_version -cin @('webull-guardian-release-v3','webull-guardian-release-v4','webull-guardian-release-v5','webull-guardian-release-v6','webull-guardian-release-v7','webull-guardian-release-v8','webull-guardian-release-v9','webull-guardian-release-v10','webull-guardian-release-v11')){
  $expectedSources+=@('app/security/webull_guardian_review_host.py','app/security/windows_review_process_supervisor.py','app/workers/windows_child_job.py')
 }
 if($manifest.schema_version -cin @('webull-guardian-release-v4','webull-guardian-release-v5','webull-guardian-release-v6','webull-guardian-release-v7','webull-guardian-release-v8','webull-guardian-release-v9','webull-guardian-release-v10','webull-guardian-release-v11')){$expectedSources+=@('app/security/webull_guardian_host_config.py','app/security/windows_protected_config.py')}
 if($manifest.schema_version -cin @('webull-guardian-release-v5','webull-guardian-release-v6','webull-guardian-release-v7','webull-guardian-release-v8','webull-guardian-release-v9','webull-guardian-release-v10','webull-guardian-release-v11')){$expectedSources+=@('app/security/windows_guardian_exchange_client.py','app/security/webull_guarded_review.py','app/scripts/webull_signed_host_fixture.py')}
 if($manifest.schema_version -cin @('webull-guardian-release-v6','webull-guardian-release-v7','webull-guardian-release-v8','webull-guardian-release-v9','webull-guardian-release-v10','webull-guardian-release-v11')){$expectedSources+=@('app/security/webull_owner_review_app.py','app/security/webull_owner_review_app.html','app/security/webull_owner_review_app.js','app/security/webull_pinned_owner_app.py','app/scripts/probe_webull_pinned_owner_app.py')}
 if($manifest.schema_version -cin @('webull-guardian-release-v7','webull-guardian-release-v8','webull-guardian-release-v9','webull-guardian-release-v10','webull-guardian-release-v11')){$expectedSources+=@('app/security/webull_owner_auth_diagnostic.py','app/scripts/webull_owner_auth_diagnostic.py')}
 if($manifest.schema_version -cin @('webull-guardian-release-v9','webull-guardian-release-v10','webull-guardian-release-v11')){$expectedSources+=@('app/security/webull_owner_credential_registry.py')}
 if($manifest.schema_version -ceq 'webull-guardian-release-v11'){$expectedSources+=@('app/scripts/webull_disposable_controls_ceremony.py')}
 if(Compare-Object @($names | Where-Object { $_.StartsWith('app/') }) @($expectedSources | Sort-Object)){throw 'Guardian source inventory mismatch.'}
 foreach($name in $names){
  if($name -notmatch '^[A-Za-z0-9_. /-]+$' -or $name.StartsWith('/') -or @($name.Split('/') | Where-Object {$_ -in @('..','.','')}).Count){throw 'Unsafe payload path.'}
  $path=Join-Path $Root $name;Ordinary $path
  $digest=$manifest.files.PSObject.Properties[$name].Value
  if($digest -cnotmatch '^[0-9a-f]{64}$' -or (Get-FileHash $path -Algorithm SHA256).Hash.ToLowerInvariant() -cne $digest){throw 'Guardian payload digest mismatch.'}
 }
 $prefix=[IO.Path]::GetFullPath($Root).TrimEnd('\')+'\'
 $actual=@(Get-ChildItem $Root -Recurse -Force | ForEach-Object {Ordinary $_.FullName;if(-not $_.PSIsContainer){$_.FullName.Substring($prefix.Length).Replace('\','/')}} | Sort-Object)
 if(Compare-Object $actual @(@($names+'guardian-release.json') | Sort-Object)){throw 'Unexpected guardian content.'}
 if([IO.File]::ReadAllText((Join-Path $Root 'python314._pth')) -cne "python314.zip`n.`npackages`napp`n"){throw 'Guardian search paths mismatch.'}
 $signature=Get-AuthenticodeSignature (Join-Path $Root 'python.exe')
 if($signature.Status -ne 'Valid' -or $signature.SignerCertificate.Subject -notmatch 'Python Software Foundation'){throw 'Python publisher verification failed.'}
 return $manifest
}
$bundle=(Resolve-Path -LiteralPath $SourceBundle).Path
$manifest=Verify-Bundle $bundle
if($ValidateOnly){Write-Output 'Pinned guardian release validated; no installation or launch.';return}
$identity=[Security.Principal.WindowsIdentity]::GetCurrent()
if(-not [Environment]::Is64BitProcess -or -not ([Security.Principal.WindowsPrincipal]::new($identity)).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)){throw 'Elevated 64-bit owner PowerShell required.'}
$guardian=Get-LocalUser AgenticGuardian;$runtime=Get-LocalUser AgenticPaperRuntime
if($guardian.Enabled -or $runtime.Enabled -or $guardian.SID -eq $identity.User -or $guardian.SID -eq $runtime.SID){throw 'Distinct disabled accounts required.'}
$ownerSid=$identity.User;$guardianSid=$guardian.SID
$adminSid=[Security.Principal.SecurityIdentifier]::new('S-1-5-32-544');$systemSid=[Security.Principal.SecurityIdentifier]::new('S-1-5-18')
function New-Protection([bool]$Directory){
 $acl=if($Directory){[Security.AccessControl.DirectorySecurity]::new()}else{[Security.AccessControl.FileSecurity]::new()}
 $acl.SetOwner($adminSid);$acl.SetAccessRuleProtection($true,$false)
 foreach($sid in @($ownerSid,$guardianSid,$adminSid,$systemSid)){
  $rights=if($sid -eq $ownerSid -or $sid -eq $guardianSid){'ReadAndExecute'}else{'FullControl'}
  $inheritance=if($Directory){'ContainerInherit,ObjectInherit'}else{'None'}
  $acl.AddAccessRule([Security.AccessControl.FileSystemAccessRule]::new($sid,$rights,$inheritance,'None','Allow'))
 }
 return $acl
}
function Fingerprint($Acl){@($Acl.GetAccessRules($true,$true,[Security.Principal.SecurityIdentifier]) | ForEach-Object {'{0}|{1}|{2}|{3}|{4}|{5}' -f $_.IdentityReference.Value,[int]$_.FileSystemRights,[int]$_.InheritanceFlags,[int]$_.PropagationFlags,[int]$_.AccessControlType,$_.IsInherited} | Sort-Object)}
function Assert-Protection([string]$Path,[bool]$Directory){
 Ordinary $Path;$acl=Get-Acl -LiteralPath $Path;$expected=New-Protection $Directory
 if(-not $acl.AreAccessRulesProtected -or $acl.GetOwner([Security.Principal.SecurityIdentifier]) -ne $adminSid -or (Compare-Object (Fingerprint $acl) (Fingerprint $expected))){throw 'Guardian exact protection mismatch.'}
}
$parent='C:\ProgramData\AgenticInvestingGuardian\Code'
Ordinary 'C:\ProgramData';Ordinary 'C:\ProgramData\AgenticInvestingGuardian'
Assert-Protection $parent $true
$target=Join-Path $parent ('GuardianRelease-'+$ExpectedManifestSha256.Substring(0,16))
if(Test-Path -LiteralPath $target){throw 'Guardian target exists; refusing overwrite or adoption.'}
New-Item -ItemType Directory $target | Out-Null
Set-Acl -LiteralPath $target -AclObject (New-Protection $true);Assert-Protection $target $true
foreach($name in @($manifest.files.PSObject.Properties.Name)+'guardian-release.json'){
 $destination=Join-Path $target $name
 $directory=Split-Path $destination -Parent
 if(-not (Test-Path -LiteralPath $directory)){New-Item -ItemType Directory $directory -Force | Out-Null}
 [IO.File]::Copy((Join-Path $bundle $name),$destination,$false)
}
$entries=@(Get-Item $target -Force)+@(Get-ChildItem $target -Recurse -Force)
foreach($entry in $entries){Ordinary $entry.FullName;Set-Acl -LiteralPath $entry.FullName -AclObject (New-Protection $entry.PSIsContainer);Assert-Protection $entry.FullName $entry.PSIsContainer}
Verify-Bundle $target | Out-Null
if((Get-LocalUser AgenticGuardian).Enabled -or (Get-LocalUser AgenticPaperRuntime).Enabled){throw 'Disabled-account verification failed.'}
Write-Output "Pinned guardian release installed: $target"
Write-Output "Verified $($entries.Count) protected objects. Accounts disabled; no service, task, state, credential, reset or trading activated."
# Retain partial installation on failure; never remove or blindly rerun it.
