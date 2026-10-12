# Owner-run bounded guardian-token fixture. Dummy files only; no service/broker/reference operations.
[CmdletBinding()]
param()
$ErrorActionPreference='Stop'
$root='C:\ProgramData\AgenticInvestingGuardian'
$principal=New-Object Security.Principal.WindowsPrincipal([Security.Principal.WindowsIdentity]::GetCurrent())
if(-not $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator) -or -not [Environment]::Is64BitProcess){throw 'Run in elevated 64-bit PowerShell.'}
$user=Get-LocalUser -Name AgenticGuardian -ErrorAction Stop
if($user.Enabled -or (Get-LocalUser -Name AgenticPaperRuntime).Enabled){throw 'Both accounts must start disabled.'}
$adminSid=New-Object Security.Principal.SecurityIdentifier('S-1-5-32-544')
foreach($area in @('Code','Config','References','Receipts','Logs')){
 $acl=Get-Acl -LiteralPath (Join-Path $root $area)
 if(-not $acl.AreAccessRulesProtected -or $acl.GetOwner([Security.Principal.SecurityIdentifier]) -ne $adminSid){throw 'Protected guardian layout required.'}
}
$probeId=[guid]::NewGuid().ToString('N')
$descriptors=@{}
foreach($area in @('Code','Config')){
 $path=Join-Path (Join-Path $root $area) "guardian-dummy-$probeId.txt"
 $stream=[IO.File]::Open($path,[IO.FileMode]::CreateNew,[IO.FileAccess]::Write)
 try{$bytes=[Text.Encoding]::UTF8.GetBytes('DUMMY-NO-SECRETS');$stream.Write($bytes,0,$bytes.Length)}finally{$stream.Dispose()}
 $descriptors[$area]=(Get-Acl -LiteralPath $path).GetSecurityDescriptorSddlForm([Security.AccessControl.AccessControlSections]::Access)
}
$childText=@'
param([string]$Root,[string]$ProbeId,[string]$ExpectedSid)
$ErrorActionPreference='Stop'
$identity=[Security.Principal.WindowsIdentity]::GetCurrent()
$principal=New-Object Security.Principal.WindowsPrincipal($identity)
if($identity.User.Value -ne $ExpectedSid -or $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)){throw 'Guardian identity/admin boundary failed.'}
$checks=@()
foreach($area in @('Code','Config')){
 $path=Join-Path (Join-Path $Root $area) "guardian-dummy-$ProbeId.txt"
 $read=[IO.File]::ReadAllText($path) -eq 'DUMMY-NO-SECRETS'
 $denied=$false
 try{[IO.File]::AppendAllText($path,'UNEXPECTED-WRITE')}catch [UnauthorizedAccessException]{$denied=$true}
 $checks+=[ordered]@{area=$area;dummy_read_passed=$read;dummy_write_denied=$denied}
}
foreach($area in @('References','Receipts','Logs')){
 $path=Join-Path (Join-Path $Root $area) "guardian-allowed-dummy-$ProbeId.txt"
 $stream=[IO.File]::Open($path,[IO.FileMode]::CreateNew,[IO.FileAccess]::Write)
 try{$bytes=[Text.Encoding]::UTF8.GetBytes('DUMMY-NO-SECRETS');$stream.Write($bytes,0,$bytes.Length)}finally{$stream.Dispose()}
 $checks+=[ordered]@{area=$area;dummy_write_read_passed=([IO.File]::ReadAllText($path) -eq 'DUMMY-NO-SECRETS')}
}
[ordered]@{schema_version='guardian-dummy-file-token-probe-v1';identity_matches=$true;is_administrator=$false;checks=$checks;observed_at_utc=[DateTime]::UtcNow.ToString('o');execution_available=$false;reset_performed=$false;trial_started=$false} | ConvertTo-Json -Depth 5 | Set-Content -LiteralPath (Join-Path (Join-Path $Root 'Receipts') "guardian-access-result-$ProbeId.json") -Encoding UTF8
'@
$childPath=Join-Path (Join-Path $root 'Code') "guardian-access-probe-$probeId.ps1"
$stream=[IO.File]::Open($childPath,[IO.FileMode]::CreateNew,[IO.FileAccess]::Write)
try{$bytes=[Text.Encoding]::UTF8.GetBytes($childText);$stream.Write($bytes,0,$bytes.Length)}finally{$stream.Dispose()}
$beforeHash=(Get-FileHash -LiteralPath $childPath -Algorithm SHA256).Hash
$password=Read-Host 'Enter the AgenticGuardian password chosen during provisioning (do not share it)' -AsSecureString
$credential=New-Object Management.Automation.PSCredential("$env:COMPUTERNAME\AgenticGuardian",$password)
$process=$null
$stdout=Join-Path (Join-Path $root 'Logs') "guardian-access-stdout-$probeId.txt"
$stderr=Join-Path (Join-Path $root 'Logs') "guardian-access-stderr-$probeId.txt"
try{
 Enable-LocalUser -Name AgenticGuardian
 $process=Start-Process -FilePath "$env:WINDIR\System32\WindowsPowerShell\v1.0\powershell.exe" -Credential $credential -WorkingDirectory $root -WindowStyle Hidden -PassThru -RedirectStandardOutput $stdout -RedirectStandardError $stderr -ArgumentList @('-NoProfile','-NonInteractive','-ExecutionPolicy','Bypass','-File',"`"$childPath`"",'-Root',$root,'-ProbeId',$probeId,'-ExpectedSid',$user.SID.Value)
 $handle=$process.Handle
 if($handle -eq [IntPtr]::Zero){throw 'Guardian process handle unavailable.'}
 if(-not $process.WaitForExit(30000)){throw 'Guardian dummy probe timed out.'}
 $process.WaitForExit()
 if($null -eq $process.ExitCode -or $process.ExitCode -ne 0){throw "Guardian dummy probe failed; diagnostic log: $stderr"}
}finally{
 try{if($process -and -not $process.HasExited){$process.Kill();$process.WaitForExit(5000)|Out-Null}}
 finally{Disable-LocalUser -Name AgenticGuardian -ErrorAction Stop;if($password){$password.Dispose()}}
}
if((Get-LocalUser -Name AgenticGuardian).Enabled -or (Get-LocalUser -Name AgenticPaperRuntime).Enabled){throw 'Disabled-account verification failed.'}
if((Get-FileHash -LiteralPath $childPath -Algorithm SHA256).Hash -ne $beforeHash){throw 'Guardian probe code changed.'}
foreach($area in @('Code','Config')){
 $path=Join-Path (Join-Path $root $area) "guardian-dummy-$probeId.txt"
 if([IO.File]::ReadAllText($path) -ne 'DUMMY-NO-SECRETS' -or (Get-Acl -LiteralPath $path).GetSecurityDescriptorSddlForm([Security.AccessControl.AccessControlSections]::Access) -ne $descriptors[$area]){throw 'Protected dummy content/DACL changed.'}
}
$resultPath=Join-Path (Join-Path $root 'Receipts') "guardian-access-result-$probeId.json"
$result=Get-Content -LiteralPath $resultPath -Raw | ConvertFrom-Json
if($result.schema_version -ne 'guardian-dummy-file-token-probe-v1' -or $result.identity_matches -ne $true -or $result.is_administrator -ne $false -or @($result.checks).Count -ne 5 -or $result.execution_available -ne $false -or $result.reset_performed -ne $false -or $result.trial_started -ne $false){throw 'Guardian result scope failed.'}
foreach($check in $result.checks){
 if($check.area -in @('Code','Config')){if($check.dummy_read_passed -ne $true -or $check.dummy_write_denied -ne $true){throw 'Guardian protected dummy check failed.'}}
 elseif($check.area -in @('References','Receipts','Logs')){if($check.dummy_write_read_passed -ne $true){throw 'Guardian dummy write check failed.'}}
 else{throw 'Unexpected guardian check.'}
}
if(@($result.checks.area | Select-Object -Unique).Count -ne 5){throw 'Repeated guardian area check.'}
foreach($area in @('References','Receipts','Logs')){
 if([IO.File]::ReadAllText((Join-Path (Join-Path $root $area) "guardian-allowed-dummy-$probeId.txt")) -ne 'DUMMY-NO-SECRETS'){throw 'Allowed dummy changed.'}
}
if((Get-Item -LiteralPath $stderr).Length -ne 0){throw 'Guardian stderr is not empty.'}
Write-Output "Guardian dummy-file token fixture passed. Account disabled again. Evidence: $resultPath"
Write-Output 'No service, pipe session, credentials or real reference used; owner standard-token deletion denial, guardian transport/lifecycle and reset remain unqualified.'
# Retain fixtures. Host crash/forced owner termination may interrupt disabling; inspect account state then.
