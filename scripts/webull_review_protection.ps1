# Shared new-item ACL function. Caller supplies owner/admin/system SIDs.
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
