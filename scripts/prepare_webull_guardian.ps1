# Owner-run creation of a DISABLED guardian and NEW EMPTY protected tree. Starts nothing.
[CmdletBinding()]
param()
$ErrorActionPreference = 'Stop'
$guardianName = 'AgenticGuardian'
$description = 'Review guardian; deployment pending'
$targetRoot = 'C:\ProgramData\AgenticInvestingGuardian'
$identity = [Security.Principal.WindowsIdentity]::GetCurrent()
$principal = New-Object Security.Principal.WindowsPrincipal($identity)
if (-not $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {
    throw 'Run directly in elevated 64-bit PowerShell. No automatic elevation is attempted.'
}
if (-not [Environment]::Is64BitProcess) { throw '64-bit PowerShell is required.' }
if ($guardianName.Length -gt 20 -or $description.Length -gt 48) { throw 'Local account metadata exceeds Windows limits.' }
if (Get-LocalUser -Name $guardianName -ErrorAction SilentlyContinue) {
    throw 'Guardian already exists; refusing password, membership or enabled-state replacement.'
}
if (Test-Path -LiteralPath $targetRoot) { throw 'Guardian tree exists; refusing adoption or permission replacement.' }
$runtime = Get-LocalUser -Name AgenticPaperRuntime -ErrorAction Stop
if ($runtime.Enabled) { throw 'Paper runtime must remain disabled.' }
$ownerSid = $identity.User
if ($ownerSid -eq $runtime.SID) { throw 'Distinct owner identity required.' }
$adminSid = New-Object Security.Principal.SecurityIdentifier('S-1-5-32-544')
$systemSid = New-Object Security.Principal.SecurityIdentifier('S-1-5-18')
foreach ($path in @('C:\ProgramData')) {
    if (((Get-Item -LiteralPath $path -Force).Attributes -band [IO.FileAttributes]::ReparsePoint) -ne 0) {
        throw 'Guardian parent is a reparse point.'
    }
}
# Standard owner/guardian users must not receive deletion authority over children
# from ProgramData itself. Administrator authority remains trusted provisioning.
$currentSids = @($identity.User.Value) + @($identity.Groups | ForEach-Object { $_.Value }) + @('S-1-1-0','S-1-5-32-545','S-1-5-11')
foreach ($rule in (Get-Acl -LiteralPath 'C:\ProgramData').GetAccessRules($true,$true,[Security.Principal.SecurityIdentifier])) {
    if ($rule.IdentityReference.Value -in @($adminSid.Value,$systemSid.Value)) { continue }
    if ($rule.IdentityReference.Value -in $currentSids -and $rule.AccessControlType -eq 'Allow' -and
        ([int]$rule.PropagationFlags -band [int][Security.AccessControl.PropagationFlags]::InheritOnly) -eq 0 -and
        ([int]$rule.FileSystemRights -band [int][Security.AccessControl.FileSystemRights]::DeleteSubdirectoriesAndFiles) -ne 0) {
        throw 'ProgramData grants standard identities child-deletion authority; review parent boundary first.'
    }
}
function Protect-GuardianDirectory([string]$Path,[string]$GuardianRights) {
    $acl = New-Object Security.AccessControl.DirectorySecurity
    $acl.SetOwner($adminSid)
    $acl.SetAccessRuleProtection($true,$false)
    foreach ($entry in @(
        @{Sid=$adminSid;Rights='FullControl'}, @{Sid=$systemSid;Rights='FullControl'},
        @{Sid=$ownerSid;Rights='ReadAndExecute'}, @{Sid=$guardianSid;Rights=$GuardianRights}
    )) {
        $acl.AddAccessRule((New-Object Security.AccessControl.FileSystemAccessRule($entry.Sid,$entry.Rights,'ContainerInherit,ObjectInherit','None','Allow')))
    }
    Set-Acl -LiteralPath $Path -AclObject $acl
    $actual = Get-Acl -LiteralPath $Path
    if (-not $actual.AreAccessRulesProtected -or
        $actual.GetOwner([Security.Principal.SecurityIdentifier]) -ne $adminSid) { throw 'Guardian directory ownership/protection mismatch.' }
    $expectedRules = @($acl.GetAccessRules($true,$true,[Security.Principal.SecurityIdentifier]) | ForEach-Object {
        '{0}|{1}|{2}|{3}|{4}|{5}' -f $_.IdentityReference.Value,[int]$_.FileSystemRights,[int]$_.InheritanceFlags,[int]$_.PropagationFlags,[int]$_.AccessControlType,$_.IsInherited
    } | Sort-Object)
    $actualRules = @($actual.GetAccessRules($true,$true,[Security.Principal.SecurityIdentifier]) | ForEach-Object {
        '{0}|{1}|{2}|{3}|{4}|{5}' -f $_.IdentityReference.Value,[int]$_.FileSystemRights,[int]$_.InheritanceFlags,[int]$_.PropagationFlags,[int]$_.AccessControlType,$_.IsInherited
    } | Sort-Object)
    if (Compare-Object $expectedRules $actualRules) { throw 'Guardian directory ACL readback mismatch.' }
}
$guardianPassword = Read-Host 'Choose a unique password for DISABLED AgenticGuardian (do not share it)' -AsSecureString
try {
    $created = New-LocalUser -Name $guardianName -Password $guardianPassword -Disabled -Description $description
    $guardianSid = $created.SID
    if ($guardianSid -eq $ownerSid -or $guardianSid -eq $runtime.SID) { throw 'Guardian identity collision.' }
    $users = Get-LocalGroup -SID 'S-1-5-32-545'
    if (-not (Get-LocalGroupMember -Group $users | Where-Object { $_.SID -eq $guardianSid })) {
        Add-LocalGroupMember -Group $users -Member $created
    }
    $groups = @(Get-LocalGroup | Where-Object {
        @(Get-LocalGroupMember -Group $_ -ErrorAction Stop | Where-Object { $_.SID -eq $guardianSid }).Count -gt 0
    })
    if (@($groups | Where-Object { $_.SID.Value -ne 'S-1-5-32-545' }).Count -gt 0) { throw 'Unexpected guardian group membership.' }
    New-Item -ItemType Directory -Path $targetRoot -ErrorAction Stop | Out-Null
    Protect-GuardianDirectory $targetRoot 'ReadAndExecute'
    foreach ($entry in @(
        @{Name='Code';Rights='ReadAndExecute'}, @{Name='Config';Rights='ReadAndExecute'},
        @{Name='References';Rights='Modify'}, @{Name='Receipts';Rights='Modify'}, @{Name='Logs';Rights='Modify'}
    )) {
        $path = Join-Path $targetRoot $entry.Name
        New-Item -ItemType Directory -Path $path -ErrorAction Stop | Out-Null
        Protect-GuardianDirectory $path $entry.Rights
    }
    if ((Get-LocalUser -Name $guardianName).Enabled -or (Get-LocalUser -Name AgenticPaperRuntime).Enabled) {
        throw 'Disabled-account verification failed.'
    }
    Write-Output 'AgenticGuardian created DISABLED with Users membership only. New empty guardian tree ACLs verified.'
    Write-Output 'Owner has ReadAndExecute; guardian may write References/Receipts/Logs. Paper runtime remains disabled with no direct tree grant.'
    Write-Output 'No service logon, service, task, credential copy, real reference, reset or trading activated.'
} finally {
    if ($guardianPassword) { $guardianPassword.Dispose() }
}
# On failure retain the partial disabled account/tree; do not delete or rerun blindly.
