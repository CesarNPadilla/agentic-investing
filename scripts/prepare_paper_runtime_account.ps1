# Run directly by the owner in elevated 64-bit PowerShell. Creates a DISABLED user only.
[CmdletBinding()]
param()
$ErrorActionPreference = 'Stop'
$runtimeName = 'AgenticPaperRuntime'
$identity = [System.Security.Principal.WindowsIdentity]::GetCurrent()
$principal = New-Object System.Security.Principal.WindowsPrincipal($identity)
if (-not $principal.IsInRole([System.Security.Principal.WindowsBuiltInRole]::Administrator)) {
    throw 'Owner must run this script in elevated PowerShell; no automatic elevation is attempted.'
}
if (Get-LocalUser -Name $runtimeName -ErrorAction SilentlyContinue) {
    throw 'Account already exists. Refusing to change its password, groups or enabled state.'
}
$runtimePassword = Read-Host 'Choose a unique password for the DISABLED paper runtime account (do not share it)' -AsSecureString
try {
    $created = New-LocalUser -Name $runtimeName -Password $runtimePassword -Disabled -Description 'Paper runtime; deployment pending'
    $usersGroup = Get-LocalGroup -SID 'S-1-5-32-545'
    if (-not (Get-LocalGroupMember -Group $usersGroup | Where-Object { $_.SID -eq $created.SID })) {
        Add-LocalGroupMember -Group $usersGroup -Member $created
    }
    $groups = @(Get-LocalGroup | Where-Object {
        @(Get-LocalGroupMember -Group $_ -ErrorAction Stop | Where-Object { $_.SID -eq $created.SID }).Count -gt 0
    })
    if (@($groups | Where-Object { $_.SID.Value -ne 'S-1-5-32-545' }).Count -gt 0) {
        throw 'Unexpected group membership. Account remains disabled; review before deployment.'
    }
    if ((Get-LocalUser -Name $runtimeName).Enabled) {
        throw 'Disabled-state verification failed. Stop and review the account.'
    }
    Write-Output 'AgenticPaperRuntime created DISABLED, with Users membership only. No services, permissions, credentials or trading were activated.'
} finally {
    if ($runtimePassword) { $runtimePassword.Dispose() }
}
