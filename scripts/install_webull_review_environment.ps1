# Installs only a pinned embedded environment into a NEW protected directory; starts nothing.
[CmdletBinding()]
param(
    [Parameter(Mandatory=$true)][string]$SourceBundle,
    [Parameter(Mandatory=$true)][ValidatePattern('^[0-9a-f]{64}$')][string]$ExpectedManifestSha256,
    [switch]$ValidateOnly
)
$ErrorActionPreference = 'Stop'
$sourceRelease = 'C:\ProgramData\AgenticInvestingPaper\OwnerControl\WebullReviewSource-3f83d3a65cead1c1'
function Assert-Ordinary([string]$Path) {
    if (((Get-Item -LiteralPath $Path -Force -ErrorAction Stop).Attributes -band [IO.FileAttributes]::ReparsePoint) -ne 0) {
        throw 'Reparse point forbidden.'
    }
}
function Test-EnvironmentBundle([string]$Root) {
    Assert-Ordinary $Root
    $manifestPath = Join-Path $Root 'environment-release.json'
    Assert-Ordinary $manifestPath
    if ((Get-FileHash -LiteralPath $manifestPath -Algorithm SHA256).Hash.ToLowerInvariant() -cne $ExpectedManifestSha256) {
        throw 'Environment manifest digest mismatch.'
    }
    $manifest = Get-Content -LiteralPath $manifestPath -Raw | ConvertFrom-Json
    if ($manifest.schema_version -cne 'webull-review-environment-v1' -or
        $manifest.scope -cne 'EMBEDDED_REVIEW_ONLY_NO_BROKER_NO_ACTIVATION' -or
        $manifest.python_version -cne '3.14.7' -or $manifest.review_source -cne $sourceRelease -or
        $manifest.execution_available -isnot [bool] -or $manifest.execution_available) { throw 'Unexpected environment scope.' }
    if (@($manifest.packages.PSObject.Properties).Count -ne 17) { throw 'Unexpected dependency inventory.' }
    $names = @($manifest.files.PSObject.Properties.Name | Sort-Object)
    if ($names.Count -ne 678) { throw 'Unexpected payload size.' }
    foreach ($name in $names) {
        if ($name -notmatch '^[A-Za-z0-9_. /-]+$' -or $name.StartsWith('/') -or
            @($name.Split('/') | Where-Object { $_ -eq '..' -or $_ -eq '.' -or $_ -eq '' }).Count) {
            throw 'Unsafe payload path.'
        }
        $file = Join-Path $Root $name
        Assert-Ordinary $file
        $expected = $manifest.files.PSObject.Properties[$name].Value
        if ($expected -cnotmatch '^[0-9a-f]{64}$' -or
            (Get-FileHash -LiteralPath $file -Algorithm SHA256).Hash.ToLowerInvariant() -cne $expected) {
            throw 'Environment payload digest mismatch.'
        }
    }
    $prefix = [IO.Path]::GetFullPath($Root).TrimEnd('\') + '\'
    $actual = @(Get-ChildItem -LiteralPath $Root -Recurse -Force | ForEach-Object {
        Assert-Ordinary $_.FullName
        if (-not $_.PSIsContainer) { $_.FullName.Substring($prefix.Length).Replace('\','/') }
    } | Sort-Object)
    if (Compare-Object $actual @(@($names + 'environment-release.json') | Sort-Object)) { throw 'Unexpected environment content.' }
    $pth = [IO.File]::ReadAllText((Join-Path $Root 'python314._pth')).Replace("`r`n","`n")
    if ($pth -cne ("python314.zip`n.`npackages`n" + $sourceRelease + "`n")) { throw 'Unexpected search path configuration.' }
    $signature = Get-AuthenticodeSignature -LiteralPath (Join-Path $Root 'python.exe')
    if ($signature.Status -ne 'Valid' -or $signature.SignerCertificate.Subject -notmatch 'Python Software Foundation') {
        throw 'Python publisher verification failed.'
    }
    return $manifest
}
$sourceRoot = (Resolve-Path -LiteralPath $SourceBundle).Path
$manifest = Test-EnvironmentBundle $sourceRoot
if ($ValidateOnly) { Write-Output 'Pinned embedded review environment verified. No installation or application launch performed.'; return }
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
foreach ($path in @('C:\ProgramData','C:\ProgramData\AgenticInvestingPaper',$parent)) { Assert-Ordinary $path }
$acl = Get-Acl -LiteralPath $parent
if (-not $acl.AreAccessRulesProtected -or $acl.GetOwner([Security.Principal.SecurityIdentifier]) -ne $adminSid) {
    throw 'Protected parent mismatch.'
}
foreach ($rule in $acl.GetAccessRules($true,$true,[Security.Principal.SecurityIdentifier])) {
    if ($rule.IdentityReference.Value -notin @($ownerSid.Value,$adminSid.Value,$systemSid.Value) -or
        $rule.AccessControlType -ne 'Allow') { throw 'Unexpected parent authority.' }
}
# Recheck the installed source without modifying it before copying the interpreter environment.
$audit = & (Join-Path $PSScriptRoot 'audit_webull_review_source.ps1') -InstalledDirectory $sourceRelease `
    -ExpectedManifestSha256 '3f83d3a65cead1c1aa1ca0d9446df741694fc520470ed6b65d140f9eb5e0ad43'
if (-not ($audit | ConvertFrom-Json).protected_source_installed) { throw 'Source audit failed.' }
. (Join-Path $PSScriptRoot 'webull_review_protection.ps1')
$target = Join-Path $parent ('WebullReviewEnvironment-' + $ExpectedManifestSha256.Substring(0,16))
if (Test-Path -LiteralPath $target) { throw 'Target exists; refusing overwrite or adoption.' }
New-Item -ItemType Directory -Path $target -ErrorAction Stop | Out-Null
Protect-NewItem $target $true
foreach ($name in @($manifest.files.PSObject.Properties.Name + 'environment-release.json')) {
    $destination = Join-Path $target $name
    $directory = [IO.Path]::GetDirectoryName($destination)
    $missing = New-Object 'System.Collections.Generic.List[string]'
    while (-not (Test-Path -LiteralPath $directory)) {
        $missing.Add($directory)
        $directory = [IO.Path]::GetDirectoryName($directory)
    }
    for ($i=$missing.Count-1; $i -ge 0; $i--) {
        New-Item -ItemType Directory -Path $missing[$i] -ErrorAction Stop | Out-Null
        Protect-NewItem $missing[$i] $true
    }
    if (Test-Path -LiteralPath $destination) { throw 'Unexpected existing payload target.' }
    Copy-Item -LiteralPath (Join-Path $sourceRoot $name) -Destination $destination -ErrorAction Stop
    Protect-NewItem $destination $false
}
$null = Test-EnvironmentBundle $target
if ((Get-LocalUser -Name AgenticPaperRuntime).Enabled) { throw 'Runtime state changed during install.' }
Write-Output ('Pinned protected review environment installed: ' + $target)
Write-Output 'Runtime remains disabled. No credentials, state, owner signing, app, service, reset or trading activated.'
Write-Output 'On failure retain the partial directory for review; do not delete or rerun blindly.'
