# Independent read-only inventory and exact ACL audit. Starts no guardian process.
[CmdletBinding()]
param([Parameter(Mandatory=$true)][ValidatePattern('^[0-9a-f]{64}$')][string]$ExpectedManifestSha256)
$ErrorActionPreference='Stop'
$target='C:\ProgramData\AgenticInvestingGuardian\Code\GuardianRelease-'+$ExpectedManifestSha256.Substring(0,16)
$validation=& (Join-Path $PSScriptRoot 'install_webull_guardian_release.ps1') -SourceBundle $target -ExpectedManifestSha256 $ExpectedManifestSha256 -ValidateOnly
if($validation -notcontains 'Pinned guardian release validated; no installation or launch.'){throw 'Guardian inventory validation failed.'}
$owner=[Security.Principal.WindowsIdentity]::GetCurrent().User
$guardian=Get-LocalUser AgenticGuardian;$runtime=Get-LocalUser AgenticPaperRuntime
if($guardian.Enabled -or $runtime.Enabled -or $guardian.SID -eq $owner -or $runtime.SID -eq $owner){throw 'Distinct disabled identities required.'}
$admin=[Security.Principal.SecurityIdentifier]::new('S-1-5-32-544');$system=[Security.Principal.SecurityIdentifier]::new('S-1-5-18')
$entries=@(Get-Item $target -Force)+@(Get-ChildItem $target -Recurse -Force)
foreach($item in $entries){
 if($item.Attributes -band [IO.FileAttributes]::ReparsePoint){throw 'Installed guardian reparse point.'}
 $acl=Get-Acl -LiteralPath $item.FullName
 if(-not $acl.AreAccessRulesProtected -or $acl.GetOwner([Security.Principal.SecurityIdentifier]) -ne $admin){throw 'Guardian owner/protection mismatch.'}
 $rules=@($acl.GetAccessRules($true,$true,[Security.Principal.SecurityIdentifier]))
 if($rules.Count -ne 4){throw 'Guardian ACL count mismatch.'}
 foreach($sid in @($owner,$guardian.SID,$admin,$system)){
  $actual=@($rules | Where-Object {$_.IdentityReference -eq $sid})
  $rights=if($sid -eq $owner -or $sid -eq $guardian.SID){[Security.AccessControl.FileSystemRights]::ReadAndExecute -bor [Security.AccessControl.FileSystemRights]::Synchronize}else{[Security.AccessControl.FileSystemRights]::FullControl}
  $inheritance=if($item.PSIsContainer){3}else{0}
  if($actual.Count -ne 1 -or $actual[0].FileSystemRights -ne $rights -or [int]$actual[0].InheritanceFlags -ne $inheritance -or [int]$actual[0].PropagationFlags -ne 0 -or $actual[0].IsInherited -or $actual[0].AccessControlType -ne 'Allow'){throw 'Guardian exact ACL mismatch.'}
 }
}
[ordered]@{schema_version='guardian-release-installed-audit-v1';observed_at_utc=[DateTime]::UtcNow.ToString('o');installed_directory=$target;manifest_sha256=$ExpectedManifestSha256;payload_files_verified=@((Get-Content -LiteralPath (Join-Path $target 'guardian-release.json') -Raw | ConvertFrom-Json).files.PSObject.Properties).Count;exact_protected_acl_objects_verified=$entries.Count;administrator_owned=$true;owner_and_guardian_read_execute_only=$true;runtime_direct_grant=$false;guardian_disabled=$true;runtime_disabled=$true;service_deployed=$false;execution_available=$false;trial_started=$false} | ConvertTo-Json
