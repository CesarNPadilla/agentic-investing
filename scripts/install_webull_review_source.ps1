# Owner-run, new source directory only. No service, interpreter, state or credential installation.
[CmdletBinding()]
param(
    [Parameter(Mandatory=$true)][string]$SourceBundle,
    [Parameter(Mandatory=$true)][ValidatePattern('^[0-9a-f]{64}$')][string]$ExpectedManifestSha256,
    [switch]$ValidateOnly
)
$ErrorActionPreference = 'Stop'
$files = @(
    'security/webull_review_signature.py', 'security/webull_review_journal.py',
    'security/webull_review_checkpoint.py', 'security/webull_owner_review_app.py',
    'security/webull_owner_review_app.html', 'security/webull_owner_review_app.js'
)
function Assert-OrdinaryPath([string]$Path) {
    $item = Get-Item -LiteralPath $Path -Force -ErrorAction Stop
    if (($item.Attributes -band [IO.FileAttributes]::ReparsePoint) -ne 0) {
        throw 'Reparse point forbidden.'
    }
}
function Test-Bundle([string]$Root) {
    Assert-OrdinaryPath $Root
    $manifestPath = Join-Path $Root 'review-release.json'
    Assert-OrdinaryPath $manifestPath
    if ((Get-FileHash -LiteralPath $manifestPath -Algorithm SHA256).Hash.ToLowerInvariant() -ne $ExpectedManifestSha256) {
        throw 'Manifest digest mismatch.'
    }
    $manifest = Get-Content -LiteralPath $manifestPath -Raw | ConvertFrom-Json
    $keys = @($manifest.PSObject.Properties.Name | Sort-Object)
    if (Compare-Object $keys @('execution_available','files','schema_version','scope')) { throw 'Unexpected manifest fields.' }
    if ($manifest.schema_version -cnotin @('webull-review-source-release-v1','webull-review-source-release-v2') -or
        $manifest.scope -cne 'REVIEW_ONLY_SOURCE_NO_EXECUTABLE_ENVIRONMENT' -or
        $manifest.execution_available -isnot [bool] -or $manifest.execution_available) { throw 'Wrong release scope.' }
    $names = @($manifest.files.PSObject.Properties.Name | Sort-Object)
    $expectedFiles = @($files)
    if ($manifest.schema_version -ceq 'webull-review-source-release-v2') {
        $expectedFiles += 'security/webull_guarded_review.py'
    }
    if (Compare-Object $names @($expectedFiles | Sort-Object)) { throw 'Wrong release inventory.' }
    $rootPrefix = [IO.Path]::GetFullPath($Root).TrimEnd('\') + '\'
    $inventory = @(Get-ChildItem -LiteralPath $Root -Recurse -Force | ForEach-Object {
        Assert-OrdinaryPath $_.FullName
        if (-not $_.PSIsContainer) { $_.FullName.Substring($rootPrefix.Length).Replace('\','/') }
    } | Sort-Object)
    if (Compare-Object $inventory @(@($expectedFiles + 'review-release.json') | Sort-Object)) { throw 'Unexpected bundle content.' }
    foreach ($name in $expectedFiles) {
        $expected = $manifest.files.PSObject.Properties[$name].Value
        if ($expected -cnotmatch '^[0-9a-f]{64}$' -or
            (Get-FileHash -LiteralPath (Join-Path $Root $name) -Algorithm SHA256).Hash.ToLowerInvariant() -cne $expected) {
            throw 'Source digest mismatch.'
        }
    }
}
$sourceRoot = (Resolve-Path -LiteralPath $SourceBundle).Path
Test-Bundle $sourceRoot
if ($ValidateOnly) { Write-Output 'Pinned review-only source bundle verified. No installation performed.'; return }
$identity = [Security.Principal.WindowsIdentity]::GetCurrent()
$principal = New-Object Security.Principal.WindowsPrincipal($identity)
if (-not $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {
    throw 'Run directly in elevated PowerShell. No automatic elevation is attempted.'
}
$runtime = Get-LocalUser -Name AgenticPaperRuntime -ErrorAction Stop
if ($runtime.Enabled) { throw 'Runtime must remain disabled.' }
$ownerSid = $identity.User
$adminSid = New-Object Security.Principal.SecurityIdentifier('S-1-5-32-544')
$systemSid = New-Object Security.Principal.SecurityIdentifier('S-1-5-18')
if ($ownerSid -eq $runtime.SID) { throw 'Distinct owner identity required.' }
$parent = 'C:\ProgramData\AgenticInvestingPaper\OwnerControl'
foreach ($path in @('C:\ProgramData','C:\ProgramData\AgenticInvestingPaper',$parent)) { Assert-OrdinaryPath $path }
$parentAcl = Get-Acl -LiteralPath $parent
if (-not $parentAcl.AreAccessRulesProtected -or
    $parentAcl.GetOwner([Security.Principal.SecurityIdentifier]) -ne $adminSid) { throw 'Protected parent mismatch.' }
$allowedSids = @($ownerSid.Value,$adminSid.Value,$systemSid.Value)
foreach ($rule in $parentAcl.GetAccessRules($true,$true,[Security.Principal.SecurityIdentifier])) {
    if ($rule.IdentityReference.Value -notin $allowedSids -or
        $rule.AccessControlType -ne 'Allow') { throw 'Unexpected parent authority.' }
}
$target = Join-Path $parent ('WebullReviewSource-' + $ExpectedManifestSha256.Substring(0,16))
if (Test-Path -LiteralPath $target) { throw 'Target already exists; refusing overwrite or adoption.' }
function Protect-NewItem([string]$Path, [bool]$Directory) {
    if ($Directory) { $acl = New-Object Security.AccessControl.DirectorySecurity }
    else { $acl = New-Object Security.AccessControl.FileSecurity }
    $acl.SetOwner($adminSid)
    $acl.SetAccessRuleProtection($true,$false)
    foreach ($sid in @($adminSid,$systemSid,$ownerSid)) {
        $rights = if ($sid -eq $ownerSid) { 'ReadAndExecute' } else { 'FullControl' }
        if ($Directory) { $inheritance = 'ContainerInherit,ObjectInherit' } else { $inheritance = 'None' }
        $rule = New-Object Security.AccessControl.FileSystemAccessRule($sid,$rights,$inheritance,'None','Allow')
        $acl.AddAccessRule($rule)
    }
    Set-Acl -LiteralPath $Path -AclObject $acl
    $actual = Get-Acl -LiteralPath $Path
    if (-not $actual.AreAccessRulesProtected -or
        $actual.GetOwner([Security.Principal.SecurityIdentifier]) -ne $adminSid) { throw 'Installed protection mismatch.' }
    $expectedRules = @($acl.GetAccessRules($true,$true,[Security.Principal.SecurityIdentifier]) | ForEach-Object {
        '{0}|{1}|{2}|{3}|{4}|{5}' -f $_.IdentityReference.Value,[int]$_.FileSystemRights,[int]$_.InheritanceFlags,[int]$_.PropagationFlags,[int]$_.AccessControlType,$_.IsInherited
    } | Sort-Object)
    $actualRules = @($actual.GetAccessRules($true,$true,[Security.Principal.SecurityIdentifier]) | ForEach-Object {
        '{0}|{1}|{2}|{3}|{4}|{5}' -f $_.IdentityReference.Value,[int]$_.FileSystemRights,[int]$_.InheritanceFlags,[int]$_.PropagationFlags,[int]$_.AccessControlType,$_.IsInherited
    } | Sort-Object)
    if (Compare-Object $expectedRules $actualRules) { throw 'Installed ACL readback differs.' }
}
# Each target is fixed within the verified OwnerControl directory. No existing object is changed.
New-Item -ItemType Directory -Path $target -ErrorAction Stop | Out-Null
Protect-NewItem $target $true
$codeDirectory = Join-Path $target 'security'
New-Item -ItemType Directory -Path $codeDirectory -ErrorAction Stop | Out-Null
Protect-NewItem $codeDirectory $true
foreach ($name in @(@((Get-Content -LiteralPath (Join-Path $sourceRoot 'review-release.json') -Raw | ConvertFrom-Json).files.PSObject.Properties.Name) + 'review-release.json')) {
    $destination = Join-Path $target $name
    if (Test-Path -LiteralPath $destination) { throw 'Unexpected existing destination.' }
    Copy-Item -LiteralPath (Join-Path $sourceRoot $name) -Destination $destination -ErrorAction Stop
    Protect-NewItem $destination $false
}
Test-Bundle $target
Write-Output ('Pinned protected review source installed: ' + $target)
Write-Output 'Runtime remains disabled. No interpreter, dependency environment, credential, journal, app, service, reset or trading installed/activated.'
Write-Output 'On failure retain partial directory for review; do not delete or rerun blindly.'
