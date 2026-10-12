# Owner-run provisioning of a NEW EMPTY tree only; no secrets, account enablement or tasks.
[CmdletBinding()]
param([Parameter(Mandatory=$true)][string]$OwnerAccount)
$ErrorActionPreference = 'Stop'
$targetRoot = 'C:\ProgramData\AgenticInvestingPaper'
$identity = [System.Security.Principal.WindowsIdentity]::GetCurrent()
$principal = New-Object System.Security.Principal.WindowsPrincipal($identity)
if (-not $principal.IsInRole([System.Security.Principal.WindowsBuiltInRole]::Administrator)) {
    throw 'Run directly in elevated PowerShell. No automatic elevation is attempted.'
}
$runtimeUser = Get-LocalUser -Name 'AgenticPaperRuntime' -ErrorAction Stop
if ($runtimeUser.Enabled) { throw 'Runtime account must remain disabled during provisioning.' }
$runtimeSid = $runtimeUser.SID
$ownerSid = (New-Object System.Security.Principal.NTAccount($OwnerAccount)).Translate([System.Security.Principal.SecurityIdentifier])
if ($ownerSid -eq $runtimeSid) { throw 'Owner and runtime must be different identities.' }
$adminSid = New-Object System.Security.Principal.SecurityIdentifier('S-1-5-32-544')
$systemSid = New-Object System.Security.Principal.SecurityIdentifier('S-1-5-18')
$memberships = @(Get-LocalGroup | Where-Object {
    @(Get-LocalGroupMember -Group $_ -ErrorAction Stop | Where-Object { $_.SID -eq $runtimeSid }).Count -gt 0
})
if (@($memberships | Where-Object { $_.SID.Value -ne 'S-1-5-32-545' }).Count -gt 0) {
    throw 'Unexpected runtime group membership.'
}
if (Test-Path -LiteralPath $targetRoot) { throw 'Deployment root already exists; refusing adoption or ACL replacement.' }
function Set-NewDirectoryAcl([string]$DirectoryPath, [string]$RuntimeRights) {
    $acl = New-Object System.Security.AccessControl.DirectorySecurity
    $acl.SetOwner($adminSid)
    $acl.SetAccessRuleProtection($true, $false)
    foreach ($sid in @($adminSid, $systemSid, $ownerSid)) {
        $rule = New-Object System.Security.AccessControl.FileSystemAccessRule($sid, 'FullControl', 'ContainerInherit,ObjectInherit', 'None', 'Allow')
        $acl.AddAccessRule($rule)
    }
    if ($RuntimeRights) {
        $rule = New-Object System.Security.AccessControl.FileSystemAccessRule($runtimeSid, $RuntimeRights, 'ContainerInherit,ObjectInherit', 'None', 'Allow')
        $acl.AddAccessRule($rule)
    }
    Set-Acl -LiteralPath $DirectoryPath -AclObject $acl
    $actual = Get-Acl -LiteralPath $DirectoryPath
    if (-not $actual.AreAccessRulesProtected -or $actual.GetOwner([System.Security.Principal.SecurityIdentifier]) -ne $adminSid) {
        throw 'Protected directory ACL/ownership verification failed.'
    }
    $expectedRules = @($acl.GetAccessRules($true,$true,[System.Security.Principal.SecurityIdentifier]) | ForEach-Object {
        '{0}|{1}|{2}|{3}|{4}|{5}' -f $_.IdentityReference.Value,[int]$_.FileSystemRights,[int]$_.InheritanceFlags,[int]$_.PropagationFlags,[int]$_.AccessControlType,$_.IsInherited
    } | Sort-Object)
    $actualRules = @($actual.GetAccessRules($true,$true,[System.Security.Principal.SecurityIdentifier]) | ForEach-Object {
        '{0}|{1}|{2}|{3}|{4}|{5}' -f $_.IdentityReference.Value,[int]$_.FileSystemRights,[int]$_.InheritanceFlags,[int]$_.PropagationFlags,[int]$_.AccessControlType,$_.IsInherited
    } | Sort-Object)
    if (Compare-Object -ReferenceObject $expectedRules -DifferenceObject $actualRules) {
        throw 'Directory ACL differs from planned rules.'
    }
}
# CreateDirectory is not used to adopt existing paths. Concurrent provisioning is unsupported.
New-Item -ItemType Directory -Path $targetRoot -ErrorAction Stop | Out-Null
Set-NewDirectoryAcl $targetRoot 'ReadAndExecute'
$layout = [ordered]@{
    Code='ReadAndExecute'; Config='ReadAndExecute'; Logs='Modify'; Outbox='Modify';
    Receipts='ReadAndExecute'; RiskState=$null; BrokerSecrets=$null; OwnerControl=$null
}
foreach ($entry in $layout.GetEnumerator()) {
    $childPath = Join-Path $targetRoot $entry.Key
    New-Item -ItemType Directory -Path $childPath -ErrorAction Stop | Out-Null
    Set-NewDirectoryAcl $childPath $entry.Value
}
Write-Output 'Empty protected layout prepared. Runtime remains disabled; no secrets, services or trading activated.'
Write-Output 'On failure retain the partial tree for review; do not delete or rerun blindly.'
