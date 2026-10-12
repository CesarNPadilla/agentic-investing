# Owner-run bounded diagnostic. No process memory, token or broker operations.
[CmdletBinding()]
param()
$ErrorActionPreference='Stop'
if(-not [Environment]::Is64BitProcess){throw 'Use elevated 64-bit Windows PowerShell.'}
$identity=[Security.Principal.WindowsIdentity]::GetCurrent()
if(-not ([Security.Principal.WindowsPrincipal]::new($identity)).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)){throw 'Use elevated 64-bit Windows PowerShell.'}
$runtime=Get-LocalUser AgenticPaperRuntime
if($runtime.Enabled -or $runtime.SID -eq $identity.User){throw 'Distinct disabled runtime required.'}
$root='C:\ProgramData\AgenticInvestingPaper'
$adminSid=[Security.Principal.SecurityIdentifier]::new('S-1-5-32-544')
foreach($directory in @($root,(Join-Path $root 'Code'),(Join-Path $root 'Logs'),(Join-Path $root 'Receipts'))){
 $item=Get-Item -LiteralPath $directory -Force
 $acl=Get-Acl -LiteralPath $directory
 if(-not $item.PSIsContainer -or ($item.Attributes -band [IO.FileAttributes]::ReparsePoint) -or -not $acl.AreAccessRulesProtected -or $acl.GetOwner([Security.Principal.SecurityIdentifier]) -ne $adminSid){throw 'Protected diagnostic layout required.'}
}
$id=[guid]::NewGuid().ToString('N')
$childPath=Join-Path $root "Code\process-environment-client-$id.ps1"
$childResult=Join-Path $root "Logs\process-environment-client-result-$id.json"
$reportPath=Join-Path $root "Receipts\process-environment-result-$id.json"
$childText=@'
param([string]$Root,[string]$ProbeId,[string]$ExpectedSid,[int]$OwnerProcessId)
$ErrorActionPreference='Stop'
Add-Type -TypeDefinition @"
using System;
using System.Runtime.InteropServices;
public static class AgenticProcessAccessProbe {
 [DllImport("kernel32.dll", SetLastError=true)] private static extern IntPtr OpenProcess(uint access, bool inherit, uint processId);
 [DllImport("kernel32.dll", SetLastError=true)] private static extern bool CloseHandle(IntPtr handle);
 public static int Probe(uint processId,uint access) {
  IntPtr handle=OpenProcess(access,false,processId);
  if(handle==IntPtr.Zero) {return Marshal.GetLastWin32Error();}
  if(!CloseHandle(handle)){throw new InvalidOperationException("Process handle close failed");}
  return 0;
 }
}
"@
$identity=[Security.Principal.WindowsIdentity]::GetCurrent()
$principal=[Security.Principal.WindowsPrincipal]::new($identity)
if($identity.User.Value -ne $ExpectedSid -or $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)){throw 'Runtime identity verification failed.'}
if([AgenticProcessAccessProbe]::Probe([uint32]$PID,0x10) -ne 0){throw 'Own-process VM_READ positive control failed.'}
$rights=[ordered]@{VM_READ=0x10;VM_WRITE=0x20;VM_OPERATION=8;CREATE_THREAD=2;DUP_HANDLE=0x40;WRITE_DAC=0x40000;WRITE_OWNER=0x80000}
$checks=@()
foreach($right in $rights.GetEnumerator()){
 $code=[AgenticProcessAccessProbe]::Probe([uint32]$OwnerProcessId,[uint32]$right.Value)
 $checks+=[pscustomobject]@{Right=$right.Key;AccessMask=[int]$right.Value;Win32Error=$code;Denied=($code -eq 5)}
}
# -ExecutionPolicy Bypass adds this one process-scoped startup variable.
# Verify its exact value; keep the replacement launch block free of ambient variables.
$expected=@('SystemRoot','WINDIR','COMSPEC','PATH','PATHEXT','PSMODULEPATH','USERPROFILE','APPDATA','LOCALAPPDATA','TEMP','TMP','PYTHONNOUSERSITE','PYTHONSAFEPATH','PSExecutionPolicyPreference')
$observed=@([Environment]::GetEnvironmentVariables().Keys)
$unexpected=@($observed | Where-Object {$_ -notin $expected})
$missing=@($expected | Where-Object {$_ -notin $observed})
$result=[ordered]@{SchemaVersion='runtime-process-environment-child-v1';ObservedAtUtc=[DateTime]::UtcNow.ToString('o');IdentityMatches=$true;IsAdministrator=$false;OwnProcessReadPositive=$true;Checks=$checks;UnexpectedEnvironmentVariableCount=$unexpected.Count;UnexpectedEnvironmentVariableNames=$unexpected;MissingEnvironmentVariableCount=$missing.Count;ProcessExecutionPolicyMatches=([Environment]::GetEnvironmentVariable('PSExecutionPolicyPreference') -ceq 'Bypass');SyntheticParentMarkerAbsent=(-not [Environment]::GetEnvironmentVariables().Contains('AGENTIC_SYNTHETIC_PARENT_SECRET'));ExecutionAvailable=$false;TrialStarted=$false}
$target=Join-Path $Root "Logs\process-environment-client-result-$ProbeId.json"
$stream=[IO.File]::Open($target,[IO.FileMode]::CreateNew,[IO.FileAccess]::Write)
try{$bytes=[Text.Encoding]::UTF8.GetBytes(($result | ConvertTo-Json -Depth 5));$stream.Write($bytes,0,$bytes.Length);$stream.Flush($true)}finally{$stream.Dispose()}
'@
$stream=[IO.File]::Open($childPath,[IO.FileMode]::CreateNew,[IO.FileAccess]::Write)
try{$bytes=[Text.Encoding]::UTF8.GetBytes($childText);$stream.Write($bytes,0,$bytes.Length)}finally{$stream.Dispose()}
$childHash=(Get-FileHash -LiteralPath $childPath -Algorithm SHA256).Hash
$runtimeHome=Join-Path $root "Logs\process-environment-home-$id"
$runtimeTemp=Join-Path $runtimeHome 'Temp'
New-Item -ItemType Directory -Path $runtimeTemp -ErrorAction Stop | Out-Null
$python=Join-Path $PSScriptRoot '..\.venv\Scripts\python.exe'
Push-Location (Join-Path $PSScriptRoot '..')
try{
 $envJson=& $python -c 'import json,sys;from workers.paper_runtime_environment import build_runtime_environment;print(json.dumps(build_runtime_environment(windows_root=sys.argv[1],runtime_profile=sys.argv[2],runtime_temp=sys.argv[3])))' $env:SystemRoot $runtimeHome $runtimeTemp
 $environmentExitCode=$LASTEXITCODE
}finally{Pop-Location}
if($environmentExitCode -ne 0){throw 'Environment preparation failed.'}
$childEnvironment=$envJson | ConvertFrom-Json
$credential=Get-Credential -UserName "$env:COMPUTERNAME\AgenticPaperRuntime" -Message 'Use the locally held runtime password, not a broker password or Windows Hello PIN.'
if(-not $credential -or $credential.UserName -ne "$env:COMPUTERNAME\AgenticPaperRuntime"){throw 'Expected runtime credential required.'}
$process=$null
$markerPrevious=[Environment]::GetEnvironmentVariable('AGENTIC_SYNTHETIC_PARENT_SECRET','Process')
$stderr=Join-Path $root "Logs\process-environment-stderr-$id.txt"
$stdout=Join-Path $root "Logs\process-environment-stdout-$id.txt"
try{
 Enable-LocalUser AgenticPaperRuntime
 [Environment]::SetEnvironmentVariable('AGENTIC_SYNTHETIC_PARENT_SECRET','DUMMY-NO-SECRETS','Process')
 $start=[Diagnostics.ProcessStartInfo]::new()
 $start.FileName="$env:WINDIR\System32\WindowsPowerShell\v1.0\powershell.exe"
 $start.WorkingDirectory=$root
 $start.UseShellExecute=$false
 $start.CreateNoWindow=$true
 $start.WindowStyle=[Diagnostics.ProcessWindowStyle]::Hidden
 $start.UserName='AgenticPaperRuntime'
 $start.Domain=$env:COMPUTERNAME
 $start.Password=$credential.Password
 $start.LoadUserProfile=$false
 $start.RedirectStandardOutput=$true
 $start.RedirectStandardError=$true
 $start.RedirectStandardInput=$true
 $start.EnvironmentVariables.Clear()
 foreach($property in $childEnvironment.PSObject.Properties){$start.EnvironmentVariables[$property.Name]=[string]$property.Value}
 $start.Arguments="-NoProfile -NonInteractive -ExecutionPolicy Bypass -File `"$childPath`" -Root $root -ProbeId $id -ExpectedSid $($runtime.SID.Value) -OwnerProcessId $PID"
 $process=[Diagnostics.Process]::Start($start)
 $process.StandardInput.Close()
 $stdoutTask=$process.StandardOutput.ReadToEndAsync()
 $stderrTask=$process.StandardError.ReadToEndAsync()
 $retainedHandle=$process.Handle
 if($retainedHandle -eq [IntPtr]::Zero){throw 'Process handle unavailable.'}
 if(-not $process.WaitForExit(30000)){throw 'Process/environment client timed out.'}
 $process.WaitForExit()
 [IO.File]::WriteAllText($stdout,$stdoutTask.GetAwaiter().GetResult())
 [IO.File]::WriteAllText($stderr,$stderrTask.GetAwaiter().GetResult())
 $exitCode=$process.ExitCode
 if($null -eq $exitCode -or $exitCode -ne 0){throw "Process/environment client failed; inspect $stderr"}
}finally{
 try{if($process -and -not $process.HasExited){$process.Kill();$process.WaitForExit(5000) | Out-Null}}
 finally{[Environment]::SetEnvironmentVariable('AGENTIC_SYNTHETIC_PARENT_SECRET',$markerPrevious,'Process');Disable-LocalUser AgenticPaperRuntime -ErrorAction Stop}
}
if((Get-LocalUser AgenticPaperRuntime).Enabled){throw 'Runtime disabling verification failed.'}
if((Get-FileHash -LiteralPath $childPath -Algorithm SHA256).Hash -ne $childHash){throw 'Retained client changed.'}
$result=Get-Content -LiteralPath $childResult -Raw | ConvertFrom-Json
if($result.SchemaVersion -ne 'runtime-process-environment-child-v1' -or $result.IdentityMatches -ne $true -or $result.IsAdministrator -ne $false -or $result.OwnProcessReadPositive -ne $true -or $result.ExecutionAvailable -ne $false -or $result.TrialStarted -ne $false -or @($result.Checks).Count -ne 7 -or $result.UnexpectedEnvironmentVariableCount -ne 0 -or @($result.UnexpectedEnvironmentVariableNames).Count -ne 0 -or $result.MissingEnvironmentVariableCount -ne 0 -or $result.ProcessExecutionPolicyMatches -ne $true -or $result.SyntheticParentMarkerAbsent -ne $true){throw "Process/environment scope or inventory failed; retained result: $childResult"}
$expectedRights=[ordered]@{VM_READ=0x10;VM_WRITE=0x20;VM_OPERATION=8;CREATE_THREAD=2;DUP_HANDLE=0x40;WRITE_DAC=0x40000;WRITE_OWNER=0x80000}
foreach($right in $expectedRights.GetEnumerator()){
 $matching=@($result.Checks | Where-Object {$_.Right -ceq $right.Key})
 if($matching.Count -ne 1 -or $matching[0].AccessMask -ne $right.Value -or $matching[0].Win32Error -ne 5 -or $matching[0].Denied -ne $true){throw 'Owner-process denial failed; no acceptance report written.'}
}
if((Get-Item -LiteralPath $stderr).Length -ne 0){throw 'Unexpected stderr; retain diagnostics.'}
$report=[ordered]@{SchemaVersion='runtime-process-environment-fixture-v1';ObservedAtUtc=[DateTime]::UtcNow.ToString('o');Scope='ELEVATED_OWNER_PROCESS_AND_EXPLICIT_CHILD_ENVIRONMENT_ONLY';ClientResult=$result;ClientSha256=$childHash.ToLowerInvariant();ClientExitCode=$exitCode;RuntimeDisabled=$true;ServiceDeployed=$false;ResetPerformed=$false;ExecutionAvailable=$false;TrialStarted=$false}
$stream=[IO.File]::Open($reportPath,[IO.FileMode]::CreateNew,[IO.FileAccess]::Write)
try{$bytes=[Text.Encoding]::UTF8.GetBytes(($report | ConvertTo-Json -Depth 7));$stream.Write($bytes,0,$bytes.Length);$stream.Flush($true)}finally{$stream.Dispose()}
Write-Output "Process/environment fixture passed. Account disabled again. Evidence: $reportPath"
Write-Output 'No process memory read/written, handles duplicated, threads created or broker called; service/passkey/reset and remote-host denial remain unqualified.'
