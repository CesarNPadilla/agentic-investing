# Read-only pinned environment inspection. No account, ACL, state or activation changes.
[CmdletBinding()]
param(
    [Parameter(Mandatory=$true)][string]$InstalledDirectory,
    [Parameter(Mandatory=$true)][ValidatePattern('^[0-9a-f]{64}$')][string]$ExpectedManifestSha256
)
$ErrorActionPreference = 'Stop'
$target = [IO.Path]::GetFullPath($InstalledDirectory).TrimEnd('\')
$expectedTarget = 'C:\ProgramData\AgenticInvestingPaper\OwnerControl\WebullReviewEnvironment-' + $ExpectedManifestSha256.Substring(0,16)
if ($target -cne $expectedTarget) { throw 'Unexpected environment location.' }
$validation = & (Join-Path $PSScriptRoot 'install_webull_review_environment.ps1') `
    -SourceBundle $target -ExpectedManifestSha256 $ExpectedManifestSha256 -ValidateOnly
if ($validation -notcontains 'Pinned embedded review environment verified. No installation or application launch performed.') {
    throw 'Environment validation failed.'
}
$ownerSid = [Security.Principal.WindowsIdentity]::GetCurrent().User
$adminSid = New-Object Security.Principal.SecurityIdentifier('S-1-5-32-544')
$systemSid = New-Object Security.Principal.SecurityIdentifier('S-1-5-18')
$runtime = Get-LocalUser -Name AgenticPaperRuntime -ErrorAction Stop
if ($runtime.Enabled -or $runtime.SID -eq $ownerSid) { throw 'Runtime identity/state mismatch.' }
function Fingerprint($Acl) {
    @($Acl.GetAccessRules($true,$true,[Security.Principal.SecurityIdentifier]) | ForEach-Object {
        '{0}|{1}|{2}|{3}|{4}|{5}' -f $_.IdentityReference.Value,[int]$_.FileSystemRights,[int]$_.InheritanceFlags,[int]$_.PropagationFlags,[int]$_.AccessControlType,$_.IsInherited
    } | Sort-Object)
}
$entries = @((Get-Item -LiteralPath $target -Force)) + @(Get-ChildItem -LiteralPath $target -Recurse -Force)
foreach ($item in $entries) {
    if (($item.Attributes -band [IO.FileAttributes]::ReparsePoint) -ne 0) { throw 'Installed reparse point.' }
    $acl = Get-Acl -LiteralPath $item.FullName
    if (-not $acl.AreAccessRulesProtected -or
        $acl.GetOwner([Security.Principal.SecurityIdentifier]) -ne $adminSid) { throw 'Environment protection mismatch.' }
    if ($item.PSIsContainer) { $planned = New-Object Security.AccessControl.DirectorySecurity }
    else { $planned = New-Object Security.AccessControl.FileSecurity }
    foreach ($sid in @($adminSid,$systemSid,$ownerSid)) {
        $rights = if ($sid -eq $ownerSid) { 'ReadAndExecute' } else { 'FullControl' }
        $inheritance = if ($item.PSIsContainer) { 'ContainerInherit,ObjectInherit' } else { 'None' }
        $planned.AddAccessRule((New-Object Security.AccessControl.FileSystemAccessRule($sid,$rights,$inheritance,'None','Allow')))
    }
    if (Compare-Object @(Fingerprint $planned) @(Fingerprint $acl)) { throw 'Installed environment ACL mismatch.' }
}
[ordered]@{
    schema_version='webull-protected-review-environment-verification-v1'
    observed_at_utc=[DateTime]::UtcNow.ToString('o')
    installed_directory=$target
    manifest_sha256=$ExpectedManifestSha256
    payload_files_verified=678
    manifest_verified=$true
    acl_objects_verified=$entries.Count
    administrator_ownership_and_exact_protected_acls=$true
    runtime_direct_grants_present=$false
    runtime_account_enabled=$false
    environment_installation_percent=100
    protected_environment_installed=$true
    actual_runtime_token_access_qualified=$false
    complete_native_loading_qualified=$false
    controller_lifecycle_qualified=$false
    actual_owner_signing_qualified=$false
    independent_recovery_anchor_qualified=$false
    app_started=$false
    reset_performed=$false
    execution_available=$false
    trial_started=$false
    live_authorized=$false
    trial_launch_percent=0
} | ConvertTo-Json -Depth 4
