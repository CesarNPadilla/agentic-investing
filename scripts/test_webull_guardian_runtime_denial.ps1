# Owner-run actual runtime pipe-DACL denial plus standard-owner positive control.
[CmdletBinding()]
param()
$ErrorActionPreference='Stop'
$pin='2cb10942c251ffec2976168ff56661181845dd2e72d0ef724a4efe32210cbad6'
$owner=[Security.Principal.WindowsIdentity]::GetCurrent()
if(-not [Environment]::Is64BitProcess -or -not ([Security.Principal.WindowsPrincipal]::new($owner)).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)){throw 'Elevated 64-bit owner PowerShell required.'}
$guardian=Get-LocalUser AgenticGuardian;$runtime=Get-LocalUser AgenticPaperRuntime
if($guardian.Enabled -or $runtime.Enabled -or $guardian.SID -eq $runtime.SID -or $owner.User -eq $runtime.SID -or $owner.User -eq $guardian.SID){throw 'Distinct disabled accounts required.'}
$audit=& (Join-Path $PSScriptRoot 'audit_webull_guardian_release.ps1') -ExpectedManifestSha256 $pin | ConvertFrom-Json
$release=$audit.installed_directory
$paper='C:\ProgramData\AgenticInvestingPaper';$root='C:\ProgramData\AgenticInvestingGuardian'
foreach($parent in @('C:\ProgramData',$paper)){if((Get-Item -LiteralPath $parent -Force).Attributes -band [IO.FileAttributes]::ReparsePoint){throw 'Paper fixture ancestor is a reparse point.'}}
foreach($area in @('Code','Receipts','Logs')){
 $item=Get-Item -LiteralPath (Join-Path $paper $area) -Force;$acl=Get-Acl -LiteralPath $item.FullName
 if(($item.Attributes -band [IO.FileAttributes]::ReparsePoint) -or -not $acl.AreAccessRulesProtected -or $acl.GetOwner([Security.Principal.SecurityIdentifier]).Value -ne 'S-1-5-32-544'){throw 'Protected paper fixture layout required.'}
}
$id=[guid]::NewGuid().ToString()
$childPath=Join-Path $paper "Code\guardian-denial-client-$id.ps1"
$runtimeReady=Join-Path $paper "Logs\guardian-denial-ready-$id.txt"
$gate=Join-Path $paper "Receipts\guardian-denial-gate-$id.txt"
$runtimeResult=Join-Path $paper "Logs\guardian-denial-client-$id.json"
$ready=Join-Path $root "Logs\guardian-pipe-ready-$id.json"
$guardianResult=Join-Path $root "Receipts\guardian-pipe-result-$id.json"
$childSource=@'
param([string]$ProbeId,[string]$ExpectedSid)
$ErrorActionPreference='Stop'
$identity=[Security.Principal.WindowsIdentity]::GetCurrent()
if($identity.User.Value -ne $ExpectedSid -or ([Security.Principal.WindowsPrincipal]::new($identity)).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)){throw 'Runtime non-admin identity required.'}
Add-Type -TypeDefinition @"
using System;
using System.Runtime.InteropServices;
public static class GuardianDeniedOpen {
 [DllImport("kernel32.dll",CharSet=CharSet.Unicode,SetLastError=true)] static extern IntPtr CreateFileW(string path,uint access,uint share,IntPtr security,uint creation,uint flags,IntPtr template);
 [DllImport("kernel32.dll",SetLastError=true)] static extern bool CloseHandle(IntPtr handle);
 public static int Open(string path,uint access) {
  IntPtr h=CreateFileW(path,access,7,IntPtr.Zero,3,0x02120000,IntPtr.Zero);
  if(h==new IntPtr(-1))return Marshal.GetLastWin32Error();
  if(!CloseHandle(h))throw new InvalidOperationException("Probe handle close failed");return 0;
 }
}
"@
$paper='C:\ProgramData\AgenticInvestingPaper'
if([GuardianDeniedOpen]::Open((Join-Path $paper 'Logs'),0x20000) -ne 0){throw 'Runtime read-control positive control failed.'}
[IO.File]::WriteAllText((Join-Path $paper "Logs\guardian-denial-ready-$ProbeId.txt"),'RUNTIME_COMPILED_READY')
$gate=Join-Path $paper "Receipts\guardian-denial-gate-$ProbeId.txt"
$deadline=[DateTime]::UtcNow.AddSeconds(30)
while(-not (Test-Path -LiteralPath $gate)){if([DateTime]::UtcNow -ge $deadline){throw 'Runtime fixture gate timed out.'};Start-Sleep -Milliseconds 25}
$name=[IO.File]::ReadAllText($gate)
if($name -notmatch '^AgenticRequest-[0-9a-f]{32}$'){throw 'Invalid runtime fixture pipe name.'}
$code=[GuardianDeniedOpen]::Open(('\\.\pipe\'+$name),0x100083)
if($code -ne 5){throw "Expected ACCESS_DENIED; observed Win32 code $code. No payload sent."}
$result=[ordered]@{schema_version='guardian-runtime-denial-child-v1';probe_id=$ProbeId;observed_at_utc=[DateTime]::UtcNow.ToString('o');runtime_identity_verified=$true;runtime_non_admin=$true;read_control_positive_passed=$true;pipe_open_win32_error=$code;pipe_dacl_denied=$true;payload_sent=$false;execution_available=$false;reset_performed=$false;trial_started=$false}
$stream=[IO.File]::Open((Join-Path $paper "Logs\guardian-denial-client-$ProbeId.json"),[IO.FileMode]::CreateNew,[IO.FileAccess]::Write)
try{$bytes=[Text.Encoding]::UTF8.GetBytes(($result | ConvertTo-Json));$stream.Write($bytes,0,$bytes.Length);$stream.Flush($true)}finally{$stream.Dispose()}
'@
$stream=[IO.File]::Open($childPath,[IO.FileMode]::CreateNew,[IO.FileAccess]::Write)
try{$bytes=[Text.Encoding]::UTF8.GetBytes($childSource);$stream.Write($bytes,0,$bytes.Length);$stream.Flush($true)}finally{$stream.Dispose()}
$childHash=(Get-FileHash -LiteralPath $childPath -Algorithm SHA256).Hash.ToLowerInvariant()
# Load current owner positive-control helper under a fresh type name, before starting either account.
$tokens=$null;$errors=$null
$ast=[Management.Automation.Language.Parser]::ParseFile((Join-Path $PSScriptRoot 'test_webull_guardian_pipe.ps1'),[ref]$tokens,[ref]$errors)
if($errors.Count){throw 'Owner helper wrapper parse failed.'}
$assignment=$ast.Find({param($node) $node -is [Management.Automation.Language.AssignmentStatementAst] -and $node.Left.Extent.Text -ceq '$clientSource'},$true)
if(-not $assignment -or $assignment.Right -isnot [Management.Automation.Language.CommandExpressionAst] -or $assignment.Right.Expression -isnot [Management.Automation.Language.StringConstantExpressionAst]){throw 'Literal owner helper source required.'}
$clientSource=$assignment.Right.Expression.Value
$typeName='GuardianDenialOwner_'+[guid]::NewGuid().ToString('N')
$ownerClient=Add-Type -TypeDefinition ($clientSource.Replace('public static class AgenticGuardianDummyPipeClient {',('public static class '+$typeName+' {'))) -PassThru
function Fixture-Start([string]$File,[string]$Arguments,[string]$Account,$Password,[string]$Work,[string]$Temp){
 $start=[Diagnostics.ProcessStartInfo]::new();$start.FileName=$File;$start.Arguments=$Arguments;$start.UserName=$Account;$start.Domain=$env:COMPUTERNAME;$start.Password=$Password
 $start.WorkingDirectory=$Work;$start.UseShellExecute=$false;$start.CreateNoWindow=$true;$start.LoadUserProfile=$false;$start.RedirectStandardError=$true;$start.RedirectStandardOutput=$true
 $start.EnvironmentVariables.Clear();foreach($name in @('SystemRoot','WINDIR')){$start.EnvironmentVariables[$name]=$env:WINDIR};$start.EnvironmentVariables['PATH']=Join-Path $env:WINDIR 'System32';foreach($name in @('TEMP','TMP')){$start.EnvironmentVariables[$name]=$Temp}
 $process=[Diagnostics.Process]::Start($start)
 try{$handle=$process.Handle;if($handle -eq [IntPtr]::Zero){throw 'Fixture process handle unavailable.'};return $process}
 catch{if($process -and -not $process.HasExited){$process.Kill();$process.WaitForExit(5000)|Out-Null};throw}
}
$guardianPassword=$null;$runtimePassword=$null;$client=$null;$server=$null
try{
 $guardianPassword=Read-Host 'Enter AgenticGuardian password locally (do not share it)' -AsSecureString
 $runtimePassword=Read-Host 'Enter AgenticPaperRuntime password locally (do not share it)' -AsSecureString
 Enable-LocalUser AgenticPaperRuntime
 $client=Fixture-Start "$env:WINDIR\System32\WindowsPowerShell\v1.0\powershell.exe" ('-NoProfile -NonInteractive -ExecutionPolicy Bypass -File "'+$childPath+'" -ProbeId '+$id+' -ExpectedSid '+$runtime.SID.Value) 'AgenticPaperRuntime' $runtimePassword $paper (Join-Path $paper 'Logs')
 $deadline=[DateTime]::UtcNow.AddSeconds(20)
 while(-not (Test-Path -LiteralPath $runtimeReady)){if($client.HasExited -or [DateTime]::UtcNow -ge $deadline){throw 'Runtime client readiness failed.'};Start-Sleep -Milliseconds 50}
 if([IO.File]::ReadAllText($runtimeReady) -ne 'RUNTIME_COMPILED_READY'){throw 'Runtime handshake failed.'}
 Enable-LocalUser AgenticGuardian
 $server=Fixture-Start (Join-Path $release 'python.exe') ('-I -B "'+(Join-Path $release 'app\scripts\probe_webull_guardian_pipe.py')+'" --guardian-sid '+$guardian.SID.Value+' --owner-sid '+$owner.User.Value+' --probe-id '+$id) 'AgenticGuardian' $guardianPassword $release (Join-Path $root 'Logs')
 $deadline=[DateTime]::UtcNow.AddSeconds(20)
 while(-not (Test-Path -LiteralPath $ready)){if($server.HasExited -or [DateTime]::UtcNow -ge $deadline){throw 'Guardian server readiness failed.'};Start-Sleep -Milliseconds 25}
 $name=(Get-Content $ready -Raw | ConvertFrom-Json).pipe_name
 if($name -notmatch '^AgenticRequest-[0-9a-f]{32}$'){throw 'Guardian pipe handshake failed.'}
 $stream=[IO.File]::Open($gate,[IO.FileMode]::CreateNew,[IO.FileAccess]::Write)
 try{$bytes=[Text.Encoding]::UTF8.GetBytes($name);$stream.Write($bytes,0,$bytes.Length);$stream.Flush($true)}finally{$stream.Dispose()}
 if(-not $client.WaitForExit(3000)){throw 'Runtime denial client timed out.'};$client.WaitForExit()
 if($null -eq $client.ExitCode -or $client.ExitCode -ne 0){throw 'Runtime denial client failed; diagnostics retained.'}
 $denial=Get-Content $runtimeResult -Raw | ConvertFrom-Json
 if($denial.schema_version -ne 'guardian-runtime-denial-child-v1' -or $denial.probe_id -ne $id -or $denial.runtime_identity_verified -ne $true -or $denial.runtime_non_admin -ne $true -or $denial.read_control_positive_passed -ne $true -or $denial.pipe_open_win32_error -ne 5 -or $denial.pipe_dacl_denied -ne $true -or $denial.payload_sent -ne $false){throw 'Runtime denial result mismatch.'}
 # Same live pipe must still accept the standard owner: distinguishes DACL denial from a missing/dead server.
 $body=[Text.Encoding]::UTF8.GetBytes('{"schema_version": "guardian-pipe-dummy-v1", "id": "'+$id+'"}')
 $ownerClient::SendStandard($name,$body)
 if(-not $server.WaitForExit(10000)){throw 'Guardian positive control timed out.'};$server.WaitForExit()
 if($null -eq $server.ExitCode -or $server.ExitCode -ne 0){throw 'Guardian positive control failed.'}
}finally{
 try{
  foreach($entry in @(@{Process=$client;Prefix='runtime';Root=$paper},@{Process=$server;Prefix='guardian';Root=$root})){
   $process=$entry.Process;if(-not $process){continue}
   if(-not $process.HasExited){$process.Kill();$process.WaitForExit(5000)|Out-Null}
   if($process.HasExited){foreach($kind in @('stderr','stdout')){$value=if($kind -eq 'stderr'){$process.StandardError.ReadToEnd()}else{$process.StandardOutput.ReadToEnd()};[IO.File]::WriteAllText((Join-Path $entry.Root "Logs\guardian-denial-$($entry.Prefix)-$kind-$id.txt"),$value)}}
  }
 }finally{
  try{Disable-LocalUser AgenticPaperRuntime -ErrorAction Stop}finally{Disable-LocalUser AgenticGuardian -ErrorAction Stop;if($guardianPassword){$guardianPassword.Dispose()};if($runtimePassword){$runtimePassword.Dispose()}}
 }
}
if((Get-LocalUser AgenticGuardian).Enabled -or (Get-LocalUser AgenticPaperRuntime).Enabled){throw 'Disabled-account verification failed.'}
if((Get-FileHash $childPath -Algorithm SHA256).Hash.ToLowerInvariant() -cne $childHash){throw 'Runtime client source changed.'}
$accepted=Get-Content $guardianResult -Raw | ConvertFrom-Json
if($accepted.schema_version -ne 'guardian-native-pipe-fixture-v1' -or $accepted.probe_id -ne $id -or $accepted.owner_pipe_identity_observed -ne $true -or $accepted.guardian_process_identity_verified -ne $true -or $accepted.synthetic_request_only -ne $true){throw 'Guardian standard-owner control failed.'}
foreach($part in @($denial,$accepted)){foreach($flag in @('execution_available','reset_performed','trial_started')){if($part.$flag -ne $false){throw 'Unexpected fixture authority.'}}}
foreach($entry in @(@{Prefix='runtime';Root=$paper},@{Prefix='guardian';Root=$root})){foreach($kind in @('stderr','stdout')){if((Get-Item (Join-Path $entry.Root "Logs\guardian-denial-$($entry.Prefix)-$kind-$id.txt")).Length -ne 0){throw 'Fixture diagnostics are not empty.'}}}
& (Join-Path $PSScriptRoot 'audit_webull_guardian_release.ps1') -ExpectedManifestSha256 $pin | Out-Null
$report=Join-Path $root "Receipts\guardian-runtime-denial-result-$id.json"
$result=[ordered]@{schema_version='guardian-runtime-denial-fixture-v1';observed_at_utc=[DateTime]::UtcNow.ToString('o');probe_id=$id;runtime=$denial;standard_owner_positive_control=$accepted;runtime_receipt_sha256=(Get-FileHash $runtimeResult -Algorithm SHA256).Hash.ToLowerInvariant();guardian_receipt_sha256=(Get-FileHash $guardianResult -Algorithm SHA256).Hash.ToLowerInvariant();child_source_sha256=$childHash;wrapper_source_sha256=(Get-FileHash $PSCommandPath -Algorithm SHA256).Hash.ToLowerInvariant();owner_helper_source_sha256=(Get-FileHash (Join-Path $PSScriptRoot 'test_webull_guardian_pipe.ps1') -Algorithm SHA256).Hash.ToLowerInvariant();installed_manifest_sha256=$pin;guardian_disabled=$true;runtime_disabled=$true;execution_available=$false;reset_performed=$false;trial_started=$false}
$stream=[IO.File]::Open($report,[IO.FileMode]::CreateNew,[IO.FileAccess]::Write)
try{$bytes=[Text.Encoding]::UTF8.GetBytes(($result | ConvertTo-Json -Depth 6));$stream.Write($bytes,0,$bytes.Length);$stream.Flush($true)}finally{$stream.Dispose()}
Write-Output "Guardian runtime DACL-denial fixture passed; standard owner accepted on the same pipe. Both accounts disabled. Evidence: $report"
Write-Output 'No runtime payload sent; synthetic owner control only. Other identities, remote hosts, service lifecycle, real approval/reference and reset remain unqualified.'
# Retain fixtures; host crash/forced wrapper termination can interrupt disabling. Inspect account state then.
