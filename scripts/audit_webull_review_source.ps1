# Read-only inspection of the pinned owner-installed source. No ACL or account changes.
[CmdletBinding()]
param(
    [Parameter(Mandatory=$true)][string]$InstalledDirectory,
    [Parameter(Mandatory=$true)][ValidatePattern('^[0-9a-f]{64}$')][string]$ExpectedManifestSha256
)
$ErrorActionPreference = 'Stop'
$expectedTarget = 'C:\ProgramData\AgenticInvestingPaper\OwnerControl\WebullReviewSource-' + $ExpectedManifestSha256.Substring(0,16)
$target = [IO.Path]::GetFullPath($InstalledDirectory).TrimEnd('\')
if ($target -cne $expectedTarget) { throw 'Unexpected protected source location.' }
$validator = Join-Path $PSScriptRoot 'install_webull_review_source.ps1'
$validation = & $validator -SourceBundle $target -ExpectedManifestSha256 $ExpectedManifestSha256 -ValidateOnly
if ($validation -notcontains 'Pinned review-only source bundle verified. No installation performed.') {
    throw 'Pinned source validation did not complete.'
}
$ownerSid = [Security.Principal.WindowsIdentity]::GetCurrent().User
$adminSid = New-Object Security.Principal.SecurityIdentifier('S-1-5-32-544')
$systemSid = New-Object Security.Principal.SecurityIdentifier('S-1-5-18')
$runtime = Get-LocalUser -Name AgenticPaperRuntime -ErrorAction Stop
if ($runtime.Enabled -or $runtime.SID -eq $ownerSid) { throw 'Runtime identity/state mismatch.' }
$entries = @((Get-Item -LiteralPath $target -Force)) + @(Get-ChildItem -LiteralPath $target -Recurse -Force)
if ($entries.Count -ne 9) { throw 'Unexpected installed object count.' }
$checked = @()
foreach ($item in $entries) {
    if (($item.Attributes -band [IO.FileAttributes]::ReparsePoint) -ne 0) { throw 'Installed reparse point.' }
    $acl = Get-Acl -LiteralPath $item.FullName
    if (-not $acl.AreAccessRulesProtected -or
        $acl.GetOwner([Security.Principal.SecurityIdentifier]) -ne $adminSid) { throw 'Installed ownership/protection mismatch.' }
    if ($item.PSIsContainer) { $planned = New-Object Security.AccessControl.DirectorySecurity }
    else { $planned = New-Object Security.AccessControl.FileSecurity }
    foreach ($sid in @($adminSid,$systemSid,$ownerSid)) {
        $rights = if ($sid -eq $ownerSid) { 'ReadAndExecute' } else { 'FullControl' }
        $inheritance = if ($item.PSIsContainer) { 'ContainerInherit,ObjectInherit' } else { 'None' }
        $planned.AddAccessRule((New-Object Security.AccessControl.FileSystemAccessRule($sid,$rights,$inheritance,'None','Allow')))
    }
    $expected = @($planned.GetAccessRules($true,$true,[Security.Principal.SecurityIdentifier]) | ForEach-Object {
        '{0}|{1}|{2}|{3}|{4}|{5}' -f $_.IdentityReference.Value,[int]$_.FileSystemRights,[int]$_.InheritanceFlags,[int]$_.PropagationFlags,[int]$_.AccessControlType,$_.IsInherited
    } | Sort-Object)
    $actual = @($acl.GetAccessRules($true,$true,[Security.Principal.SecurityIdentifier]) | ForEach-Object {
        '{0}|{1}|{2}|{3}|{4}|{5}' -f $_.IdentityReference.Value,[int]$_.FileSystemRights,[int]$_.InheritanceFlags,[int]$_.PropagationFlags,[int]$_.AccessControlType,$_.IsInherited
    } | Sort-Object)
    if (Compare-Object $expected $actual) { throw 'Installed ACL differs from exact planned rights.' }
    $relative = if ($item.FullName -eq $target) { '.' } else { $item.FullName.Substring($target.Length + 1).Replace('\','/') }
    $checked += [ordered]@{relative_path=$relative;administrator_owned=$true;protected_exact_acl=$true;runtime_direct_grant=$false}
}
$record = [ordered]@{
    schema_version='webull-protected-review-source-verification-v1'
    observed_at_utc=[DateTime]::UtcNow.ToString('o')
    installed_directory=$target
    manifest_sha256=$ExpectedManifestSha256
    installed_source_files_verified=@((Get-Content -LiteralPath (Join-Path $target 'review-release.json') -Raw | ConvertFrom-Json).files.PSObject.Properties).Count
    manifest_verified=$true
    installed_objects_acl_verified=$checked.Count
    checked_objects=$checked
    runtime_account_enabled=$false
    protected_source_installed=$true
    source_installation_percent=100
    protected_interpreter_dependencies_qualified=$false
    actual_runtime_token_access_qualified=$false
    independent_recovery_anchor_qualified=$false
    actual_owner_signing_qualified=$false
    service_deployed=$false
    reset_performed=$false
    execution_available=$false
    trial_started=$false
    live_authorized=$false
    trial_launch_percent=0
}
$record | ConvertTo-Json -Depth 6
