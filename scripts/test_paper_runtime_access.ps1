# Owner-run, bounded dummy-file test. No brokerage access or trading activation.
[CmdletBinding()]
param()
$ErrorActionPreference='Stop'
$root='C:\ProgramData\AgenticInvestingPaper'
$identity=[System.Security.Principal.WindowsIdentity]::GetCurrent()
$principal=New-Object System.Security.Principal.WindowsPrincipal($identity)
if(-not $principal.IsInRole([System.Security.Principal.WindowsBuiltInRole]::Administrator)){throw 'Run in elevated 64-bit PowerShell.'}
$user=Get-LocalUser -Name 'AgenticPaperRuntime' -ErrorAction Stop
if($user.Enabled){throw 'Account must start disabled; refusing to adopt an active runtime.'}
$adminSid=New-Object System.Security.Principal.SecurityIdentifier('S-1-5-32-544')
$areas=@('Code','Config','Receipts','RiskState','BrokerSecrets','OwnerControl','Logs','Outbox')
foreach($area in $areas){
    $acl=Get-Acl -LiteralPath (Join-Path $root $area)
    if(-not $acl.AreAccessRulesProtected -or $acl.GetOwner([System.Security.Principal.SecurityIdentifier]) -ne $adminSid){throw 'Protected layout required.'}
}
$probeId=[guid]::NewGuid().ToString('N')
$fixtureName="access-fixture-$probeId.txt"
$fixtureAreas=@('Code','Config','Receipts','RiskState','BrokerSecrets','OwnerControl')
$fixtureDescriptors=@{}
foreach($area in $fixtureAreas){
    $path=Join-Path (Join-Path $root $area) $fixtureName
    $stream=[System.IO.File]::Open($path,[System.IO.FileMode]::CreateNew,[System.IO.FileAccess]::Write)
    try{$bytes=[Text.Encoding]::UTF8.GetBytes('DUMMY-NO-SECRETS');$stream.Write($bytes,0,$bytes.Length)}finally{$stream.Dispose()}
    $fixtureAcl=Get-Acl -LiteralPath $path
    $fixtureDescriptors[$area]=[Convert]::ToBase64String($fixtureAcl.GetSecurityDescriptorBinaryForm())
}
$aclInputPath=Join-Path (Join-Path $root 'Code') "access-acl-input-$probeId.json"
[System.IO.File]::WriteAllText($aclInputPath,($fixtureDescriptors | ConvertTo-Json))
$aclInputHash=(Get-FileHash -LiteralPath $aclInputPath -Algorithm SHA256).Hash
$childPath=Join-Path (Join-Path $root 'Code') "access-probe-$probeId.ps1"
$childText=@'
param([string]$Root,[string]$ProbeId,[string]$ExpectedSid)
$ErrorActionPreference='Stop'
$identity=[System.Security.Principal.WindowsIdentity]::GetCurrent()
$principal=New-Object System.Security.Principal.WindowsPrincipal($identity)
$checks=@()
$descriptors=Get-Content -LiteralPath (Join-Path (Join-Path $Root 'Code') "access-acl-input-$ProbeId.json") -Raw | ConvertFrom-Json
foreach($area in @('Code','Config','Receipts','RiskState','BrokerSecrets','OwnerControl')){
    $path=Join-Path (Join-Path $Root $area) "access-fixture-$ProbeId.txt"
    $readAllowed=$area -in @('Code','Config','Receipts')
    $readSuccess=$false
    try{$readSuccess=[System.IO.File]::ReadAllText($path) -eq 'DUMMY-NO-SECRETS'}catch [System.UnauthorizedAccessException]{}
    $writeDenied=$false
    try{[System.IO.File]::AppendAllText($path,'UNEXPECTED-WRITE')}catch [System.UnauthorizedAccessException]{$writeDenied=$true}
    # Try writing only the existing DACL to an isolated dummy file, never a directory.
    # Owner-provided descriptors avoid confusing READ_CONTROL denial with WRITE_DAC denial.
    $fixtureSecurity=New-Object System.Security.AccessControl.FileSecurity
    $fixtureSecurity.SetSecurityDescriptorBinaryForm([Convert]::FromBase64String($descriptors.$area),[System.Security.AccessControl.AccessControlSections]::Access)
    $aclWriteDenied=$false
    try{[System.IO.File]::SetAccessControl($path,$fixtureSecurity)}catch [System.UnauthorizedAccessException]{$aclWriteDenied=$true}
    $checks+=[pscustomobject]@{Area=$area;ReadMatches=($readSuccess -eq $readAllowed);WriteDenied=$writeDenied;AclWriteDenied=$aclWriteDenied}
}
foreach($area in @('Logs','Outbox')){
    $path=Join-Path (Join-Path $Root $area) "allowed-fixture-$ProbeId.txt"
    [System.IO.File]::WriteAllText($path,'DUMMY-NO-SECRETS')
    $checks+=[pscustomobject]@{Area=$area;WriteAllowed=([System.IO.File]::ReadAllText($path) -eq 'DUMMY-NO-SECRETS')}
}
$report=[pscustomobject]@{SchemaVersion='runtime-file-and-dacl-probe-v2';IdentityMatches=($identity.User.Value -eq $ExpectedSid);IsAdministrator=$principal.IsInRole([System.Security.Principal.WindowsBuiltInRole]::Administrator);Checks=$checks;ObservedAtUtc=[DateTime]::UtcNow.ToString('o');ExecutionAvailable=$false;TrialStarted=$false}
$report | ConvertTo-Json -Depth 5 | Set-Content -LiteralPath (Join-Path (Join-Path $Root 'Logs') "access-result-$ProbeId.json") -Encoding utf8
'@
[System.IO.File]::WriteAllText($childPath,$childText)
$beforeHash=(Get-FileHash -LiteralPath $childPath -Algorithm SHA256).Hash
$credential=Get-Credential -UserName "$env:COMPUTERNAME\AgenticPaperRuntime" -Message 'Use the password you chose when creating AgenticPaperRuntime (not Webull password or Windows Hello PIN)'
if(-not $credential -or $credential.UserName -ne "$env:COMPUTERNAME\AgenticPaperRuntime"){throw 'Expected runtime credential required.'}
$process=$null
try{
    Enable-LocalUser -Name 'AgenticPaperRuntime'
    $stdoutPath=Join-Path (Join-Path $root 'Logs') "access-stdout-$probeId.txt"
    $stderrPath=Join-Path (Join-Path $root 'Logs') "access-stderr-$probeId.txt"
    # Process-only policy for this owner-generated fixed dummy probe; machine policy unchanged.
    $process=Start-Process -FilePath "$env:WINDIR\System32\WindowsPowerShell\v1.0\powershell.exe" -Credential $credential -WorkingDirectory $root -WindowStyle Hidden -PassThru -RedirectStandardOutput $stdoutPath -RedirectStandardError $stderrPath -ArgumentList @('-NoProfile','-NonInteractive','-ExecutionPolicy','Bypass','-File',"`"$childPath`"",'-Root',$root,'-ProbeId',$probeId,'-ExpectedSid',$user.SID.Value)
    # Retain the process handle before exit so the alternate-credential process remains queryable.
    $retainedProcessHandle=$process.Handle
    if($retainedProcessHandle -eq [IntPtr]::Zero){throw 'Runtime process handle unavailable.'}
    if(-not $process.WaitForExit(30000)){throw 'Runtime probe timed out.'}
    $process.WaitForExit()
    $exitCode=$process.ExitCode
    if($null -eq $exitCode){throw "Runtime process exit code unavailable; inspect retained result and logs: $stderrPath"}
    if($exitCode -ne 0){
        if(Test-Path -LiteralPath $stderrPath){Get-Content -LiteralPath $stderrPath | Write-Host}
        throw "Runtime probe failed (exit $exitCode); diagnostic error log: $stderrPath"
    }
}finally{
    try{
        if($process -and -not $process.HasExited){$process.Kill();$process.WaitForExit(5000) | Out-Null}
    }finally{
        Disable-LocalUser -Name 'AgenticPaperRuntime' -ErrorAction Stop
    }
}
if((Get-LocalUser -Name 'AgenticPaperRuntime').Enabled){throw 'Account disabling verification failed.'}
if((Get-FileHash -LiteralPath $childPath -Algorithm SHA256).Hash -ne $beforeHash){throw 'Probe code changed.'}
if((Get-FileHash -LiteralPath $aclInputPath -Algorithm SHA256).Hash -ne $aclInputHash){throw 'Probe ACL inputs changed.'}
foreach($area in $fixtureAreas){if([System.IO.File]::ReadAllText((Join-Path (Join-Path $root $area) $fixtureName)) -ne 'DUMMY-NO-SECRETS'){throw 'Protected fixture changed.'}}
foreach($area in $fixtureAreas){
    $fixtureAcl=Get-Acl -LiteralPath (Join-Path (Join-Path $root $area) $fixtureName)
    $expected=New-Object System.Security.AccessControl.FileSecurity
    $expected.SetSecurityDescriptorBinaryForm([Convert]::FromBase64String($fixtureDescriptors[$area]))
    if($fixtureAcl.GetSecurityDescriptorSddlForm([System.Security.AccessControl.AccessControlSections]::Access) -ne $expected.GetSecurityDescriptorSddlForm([System.Security.AccessControl.AccessControlSections]::Access)){throw 'Dummy fixture DACL changed.'}
}
$resultPath=Join-Path (Join-Path $root 'Logs') "access-result-$probeId.json"
$result=Get-Content -LiteralPath $resultPath -Raw | ConvertFrom-Json
if($result.SchemaVersion -ne 'runtime-file-and-dacl-probe-v2' -or $result.ExecutionAvailable -ne $false -or $result.TrialStarted -ne $false -or -not $result.IdentityMatches -or $result.IsAdministrator -or @($result.Checks).Count -ne 8){throw 'Runtime identity/check inventory failed.'}
foreach($check in $result.Checks){
    if($check.Area -in $fixtureAreas){if(-not $check.ReadMatches -or -not $check.WriteDenied -or -not $check.AclWriteDenied){throw 'Protected access/DACL check failed.'}}
    elseif(-not $check.WriteAllowed){throw 'Allowed write check failed.'}
}
Write-Output "Bounded runtime file-access and dummy-file DACL checks passed. Account disabled again. Evidence: $resultPath"
Write-Output 'Dummy fixtures retained; directory ACL escalation, controller/reset and broker isolation remain unqualified.'
