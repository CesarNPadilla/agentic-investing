# Owner-run, handle-only private-file boundary test. No ACL/owner mutation or broker access.
[CmdletBinding()]
param()
$ErrorActionPreference='Stop'
if(-not [Environment]::Is64BitProcess){throw 'Use elevated 64-bit Windows PowerShell.'}
$identity=[Security.Principal.WindowsIdentity]::GetCurrent()
$principal=[Security.Principal.WindowsPrincipal]::new($identity)
if(-not $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)){throw 'Use elevated 64-bit Windows PowerShell.'}
$runtime=Get-LocalUser AgenticPaperRuntime -ErrorAction Stop
if($runtime.Enabled -or $runtime.SID -eq $identity.User){throw 'Distinct disabled runtime identity required.'}
$root='C:\ProgramData\AgenticInvestingPaper'
$privateRoot='C:\Users\cesar\AppData\Local\AgenticInvesting'
$targetPaths=@{WebullProduction=(Join-Path $privateRoot 'webull.env');WebullSandbox=(Join-Path $privateRoot 'webull.sandbox.env');OwnerPublicCredential=(Join-Path $privateRoot 'owner-passkey-enrollment.json');SelectedCashAccount=(Join-Path $privateRoot 'webull-sandbox-cash-selection.json')}
$areas=@('WebullProduction','WebullSandbox','OwnerPublicCredential','SelectedCashAccount')
$adminSid=[Security.Principal.SecurityIdentifier]::new('S-1-5-32-544')
$sections=[Security.AccessControl.AccessControlSections]::Access -bor [Security.AccessControl.AccessControlSections]::Owner
$before=@{}
$metadataBefore=@{}
foreach($directory in @($root,(Join-Path $root 'Code'),(Join-Path $root 'Logs'),(Join-Path $root 'Receipts'))){
 $item=Get-Item -LiteralPath $directory -Force
 $acl=Get-Acl -LiteralPath $directory
 if(-not $item.PSIsContainer -or ($item.Attributes -band [IO.FileAttributes]::ReparsePoint) -or -not $acl.AreAccessRulesProtected -or $acl.GetOwner([Security.Principal.SecurityIdentifier]) -ne $adminSid){throw 'Protected diagnostic output layout required.'}
}
foreach($area in $areas){
    $path=$targetPaths[$area]
    $item=Get-Item -LiteralPath $path -Force
    if($item.PSIsContainer -or ($item.Attributes -band [IO.FileAttributes]::ReparsePoint)){throw 'Existing non-reparse files required.'}
    $acl=Get-Acl -LiteralPath $path
    if($acl.GetOwner([Security.Principal.SecurityIdentifier]) -eq $runtime.SID){throw 'Private file owned by runtime; refuse qualification.'}
    $before[$area]=$acl.GetSecurityDescriptorSddlForm($sections)
    $metadataBefore[$area]=@($item.Length,$item.LastWriteTimeUtc.Ticks)
}
$id=[guid]::NewGuid().ToString('N')
$childPath=Join-Path $root "Code\private-file-boundary-client-$id.ps1"
$childResult=Join-Path $root "Logs\private-file-boundary-client-result-$id.json"
$reportPath=Join-Path $root "Receipts\private-file-boundary-result-$id.json"
$childText=@'
param([string]$Root,[string]$ProbeId,[string]$ExpectedSid)
$ErrorActionPreference='Stop'
Add-Type -TypeDefinition @"
using System;
using System.Runtime.InteropServices;
public static class AgenticPrivateFileAccessProbe {
 [DllImport("kernel32.dll", CharSet=CharSet.Unicode, SetLastError=true)]
 private static extern IntPtr CreateFileW(string path, uint access, uint sharing, IntPtr security, uint creation, uint flags, IntPtr template);
 [DllImport("kernel32.dll", SetLastError=true)]
 private static extern bool CloseHandle(IntPtr handle);
 public static int OpenExisting(string path, uint access) {
  IntPtr handle=CreateFileW(path,access,7,IntPtr.Zero,3,0x02000000,IntPtr.Zero);
  if(handle==new IntPtr(-1)) {return Marshal.GetLastWin32Error();}
  if(!CloseHandle(handle)) {throw new InvalidOperationException("Directory handle close failed");}
  return 0;
 }
}
"@
$identity=[Security.Principal.WindowsIdentity]::GetCurrent()
$principal=[Security.Principal.WindowsPrincipal]::new($identity)
if($identity.User.Value -ne $ExpectedSid -or $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)){throw 'Runtime identity verification failed.'}
# Positive control: a new dummy file in Logs, with read/write handles but no content reads.
$positive=Join-Path $Root "Logs\private-file-boundary-positive-$ProbeId"
if(Test-Path -LiteralPath $positive){throw 'Positive-control path already exists.'}
New-Item -ItemType File -Path $positive -ErrorAction Stop | Out-Null
foreach($mask in @(1,2)){if([AgenticPrivateFileAccessProbe]::OpenExisting($positive,[uint32]$mask) -ne 0){throw 'Read/write handle positive control failed.'}}
$privateRoot='C:\Users\cesar\AppData\Local\AgenticInvesting'
$targetPaths=@{WebullProduction=(Join-Path $privateRoot 'webull.env');WebullSandbox=(Join-Path $privateRoot 'webull.sandbox.env');OwnerPublicCredential=(Join-Path $privateRoot 'owner-passkey-enrollment.json');SelectedCashAccount=(Join-Path $privateRoot 'webull-sandbox-cash-selection.json')}
$rights=[ordered]@{READ_DATA=1;WRITE_DATA=2;DELETE=0x10000;WRITE_DAC=0x40000;WRITE_OWNER=0x80000}
$checks=@()
foreach($area in @('WebullProduction','WebullSandbox','OwnerPublicCredential','SelectedCashAccount')){
    $path=$targetPaths[$area]
    foreach($right in $rights.GetEnumerator()){
        $errorCode=[AgenticPrivateFileAccessProbe]::OpenExisting($path,[uint32]$right.Value)
        $checks+=[pscustomobject]@{Area=$area;Right=$right.Key;AccessMask=[int]$right.Value;Win32Error=$errorCode;Denied=($errorCode -eq 5)}
    }
}
$result=[pscustomobject]@{SchemaVersion='runtime-private-file-boundary-child-v1';ObservedAtUtc=[DateTime]::UtcNow.ToString('o');IdentityMatches=$true;IsAdministrator=$false;PositiveReadWriteHandlesGranted=$true;Checks=$checks;ExecutionAvailable=$false;TrialStarted=$false}
$target=Join-Path $Root "Logs\private-file-boundary-client-result-$ProbeId.json"
$stream=[IO.File]::Open($target,[IO.FileMode]::CreateNew,[IO.FileAccess]::Write)
try{$bytes=[Text.Encoding]::UTF8.GetBytes(($result | ConvertTo-Json -Depth 5));$stream.Write($bytes,0,$bytes.Length);$stream.Flush($true)}finally{$stream.Dispose()}
'@
$stream=[IO.File]::Open($childPath,[IO.FileMode]::CreateNew,[IO.FileAccess]::Write)
try{$bytes=[Text.Encoding]::UTF8.GetBytes($childText);$stream.Write($bytes,0,$bytes.Length)}finally{$stream.Dispose()}
$childHash=(Get-FileHash -LiteralPath $childPath -Algorithm SHA256).Hash
$credential=Get-Credential -UserName "$env:COMPUTERNAME\AgenticPaperRuntime" -Message 'Use the locally held AgenticPaperRuntime password, not a broker password or Windows Hello PIN.'
if(-not $credential -or $credential.UserName -ne "$env:COMPUTERNAME\AgenticPaperRuntime"){throw 'Expected runtime credential required.'}
$process=$null
$exitCode=$null
try{
    Enable-LocalUser AgenticPaperRuntime
    $stderr=Join-Path $root "Logs\private-file-boundary-stderr-$id.txt"
    $stdout=Join-Path $root "Logs\private-file-boundary-stdout-$id.txt"
    $process=Start-Process -FilePath "$env:WINDIR\System32\WindowsPowerShell\v1.0\powershell.exe" -Credential $credential -WorkingDirectory $root -WindowStyle Hidden -PassThru -RedirectStandardError $stderr -RedirectStandardOutput $stdout -ArgumentList @('-NoProfile','-NonInteractive','-ExecutionPolicy','Bypass','-File',"`"$childPath`"",'-Root',$root,'-ProbeId',$id,'-ExpectedSid',$runtime.SID.Value)
    $retainedHandle=$process.Handle
    if($retainedHandle -eq [IntPtr]::Zero){throw 'Runtime process handle unavailable.'}
    if(-not $process.WaitForExit(30000)){throw 'Private-file boundary probe timed out.'}
    $process.WaitForExit()
    $exitCode=$process.ExitCode
    if($null -eq $exitCode -or $exitCode -ne 0){throw "Private-file boundary client failed; inspect $stderr"}
}finally{
    try{if($process -and -not $process.HasExited){$process.Kill();$process.WaitForExit(5000) | Out-Null}}
    finally{Disable-LocalUser AgenticPaperRuntime -ErrorAction Stop}
}
if((Get-LocalUser AgenticPaperRuntime).Enabled){throw 'Runtime disabling verification failed.'}
if((Get-FileHash -LiteralPath $childPath -Algorithm SHA256).Hash -ne $childHash){throw 'Retained client changed.'}
foreach($area in $areas){
    $path=$targetPaths[$area]
    if((Get-Acl -LiteralPath $path).GetSecurityDescriptorSddlForm($sections) -cne $before[$area]){throw 'Private-file owner or DACL changed.'}
    $item=Get-Item -LiteralPath $path -Force
    if($item.Length -ne $metadataBefore[$area][0] -or $item.LastWriteTimeUtc.Ticks -ne $metadataBefore[$area][1]){throw 'Private-file metadata changed.'}
}
$result=Get-Content -LiteralPath $childResult -Raw | ConvertFrom-Json
if($result.SchemaVersion -ne 'runtime-private-file-boundary-child-v1' -or $result.IdentityMatches -ne $true -or $result.IsAdministrator -ne $false -or $result.PositiveReadWriteHandlesGranted -ne $true -or $result.ExecutionAvailable -ne $false -or $result.TrialStarted -ne $false -or @($result.Checks).Count -ne 20){throw 'Private-file boundary result scope failed.'}
$expectedRights=[ordered]@{READ_DATA=1;WRITE_DATA=2;DELETE=0x10000;WRITE_DAC=0x40000;WRITE_OWNER=0x80000}
foreach($area in $areas){foreach($right in $expectedRights.GetEnumerator()){
    $matching=@($result.Checks | Where-Object {$_.Area -ceq $area -and $_.Right -ceq $right.Key})
    if($matching.Count -ne 1 -or $matching[0].AccessMask -ne $right.Value -or $matching[0].Win32Error -ne 5 -or $matching[0].Denied -ne $true){throw 'Private-file boundary denial check failed; no acceptance report written.'}
}}
if((Get-Item -LiteralPath $stderr).Length -ne 0){throw 'Unexpected runtime stderr; retain diagnostics for review.'}
$report=[ordered]@{SchemaVersion='runtime-private-file-boundary-fixture-v1';ObservedAtUtc=[DateTime]::UtcNow.ToString('o');Scope='NATIVE_PRIVATE_FILE_HANDLES_ONLY';ClientResult=$result;ClientSha256=$childHash.ToLowerInvariant();ClientExitCode=$exitCode;PrivateFileOwnersDaclsAndMetadataUnchanged=$true;RuntimeDisabled=$true;ServiceDeployed=$false;ResetPerformed=$false;ExecutionAvailable=$false;TrialStarted=$false}
$stream=[IO.File]::Open($reportPath,[IO.FileMode]::CreateNew,[IO.FileAccess]::Write)
try{$bytes=[Text.Encoding]::UTF8.GetBytes(($report | ConvertTo-Json -Depth 7));$stream.Write($bytes,0,$bytes.Length);$stream.Flush($true)}finally{$stream.Dispose()}
Write-Output "Private-file boundary fixture passed (20 denied handles). Account disabled again. Evidence: $reportPath"
Write-Output 'No credential contents read or broker calls; service, passkey/reset, process/environment isolation and remote-host denial remain unqualified.'
