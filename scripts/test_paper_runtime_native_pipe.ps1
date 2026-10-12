# Owner-run synthetic native Python transport fixture. No broker or reset authority.
[CmdletBinding()]
param()
$ErrorActionPreference='Stop'
$identity=[Security.Principal.WindowsIdentity]::GetCurrent()
$principal=New-Object Security.Principal.WindowsPrincipal($identity)
if(-not $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)){throw 'Run in elevated 64-bit Windows PowerShell.'}
$runtime=Get-LocalUser AgenticPaperRuntime
if($runtime.Enabled -or $runtime.SID -eq $identity.User){throw 'Distinct disabled runtime required.'}
$root='C:\ProgramData\AgenticInvestingPaper'
foreach($area in @('Code','Receipts','RiskState','Logs')){
 $acl=Get-Acl -LiteralPath (Join-Path $root $area)
 if(-not $acl.AreAccessRulesProtected -or $acl.GetOwner([Security.Principal.SecurityIdentifier]).Value -ne 'S-1-5-32-544'){throw 'Protected fixture layout required.'}
}
$id=[guid]::NewGuid().ToString('N')
$requestId=[guid]::NewGuid().ToString()
$ready=Join-Path (Join-Path $root 'Receipts') "native-pipe-ready-$id.json"
$report=Join-Path (Join-Path $root 'Receipts') "native-pipe-result-$id.json"
$gate=Join-Path (Join-Path $root 'Receipts') "native-pipe-gate-$id.txt"
$journal=Join-Path (Join-Path $root 'RiskState') "native-pipe-synthetic-$id.sqlite"
$childPath=Join-Path (Join-Path $root 'Code') "native-pipe-client-$id.ps1"
$childText=@'
param([string]$PipeName,[string]$RequestId)
$ErrorActionPreference='Stop'
$rights=[IO.Pipes.PipeAccessRights]::ReadData -bor [IO.Pipes.PipeAccessRights]::WriteData -bor [IO.Pipes.PipeAccessRights]::ReadAttributes -bor [IO.Pipes.PipeAccessRights]::Synchronize
$client=[IO.Pipes.NamedPipeClientStream]::new('.',$PipeName,$rights,[IO.Pipes.PipeOptions]::None,[Security.Principal.TokenImpersonationLevel]::Identification,[IO.HandleInheritability]::None)
try{
 $client.Connect(3000)
 $json=[ordered]@{schema_version='webull-control-request-v1';action='REQUEST_RESET_REVIEW';account_binding_sha256=('a'*64);expected_state_sha256=('b'*64);request_id=$RequestId} | ConvertTo-Json -Compress
 $body=[Text.Encoding]::UTF8.GetBytes($json)
 $header=[BitConverter]::GetBytes([uint32]$body.Length)
 if([BitConverter]::IsLittleEndian){[Array]::Reverse($header)}
 $client.Write($header,0,4);$client.Write($body,0,$body.Length);$client.Flush()
 Start-Sleep -Seconds 2
}finally{$client.Dispose()}
'@
$stream=[IO.File]::Open($childPath,[IO.FileMode]::CreateNew,[IO.FileAccess]::Write)
try{$bytes=[Text.Encoding]::UTF8.GetBytes($childText);$stream.Write($bytes,0,$bytes.Length)}finally{$stream.Dispose()}
$childHash=(Get-FileHash -LiteralPath $childPath -Algorithm SHA256).Hash
$credential=Get-Credential -UserName "$env:COMPUTERNAME\AgenticPaperRuntime" -Message 'Enter the locally held AgenticPaperRuntime password; never share it.'
if(-not $credential -or $credential.UserName -ne "$env:COMPUTERNAME\AgenticPaperRuntime"){throw 'Expected runtime credential required.'}
$server=$client=$null
$repo=Split-Path $PSScriptRoot -Parent
try{
 $server=Start-Process -FilePath (Join-Path $repo '.venv\Scripts\python.exe') -WorkingDirectory $repo -WindowStyle Hidden -PassThru -RedirectStandardOutput (Join-Path (Join-Path $root 'Logs') "native-server-stdout-$id.txt") -RedirectStandardError (Join-Path (Join-Path $root 'Logs') "native-server-stderr-$id.txt") -ArgumentList @('-m','scripts.probe_paper_native_pipe','--runtime-sid',$runtime.SID.Value,'--ready-file',$ready,'--report-file',$report,'--journal-file',$journal,'--startup-gate',$gate)
 $serverHandle=$server.Handle
 if($serverHandle -eq [IntPtr]::Zero){throw 'Native server handle unavailable.'}
 $timer=[Diagnostics.Stopwatch]::StartNew()
 while(-not (Test-Path -LiteralPath $ready)){
  if($server.HasExited -or $timer.ElapsedMilliseconds -ge 10000){throw "Native fixture startup failed; server error log: $(Join-Path (Join-Path $root 'Logs') "native-server-stderr-$id.txt")"}
  Start-Sleep -Milliseconds 50
 }
 # The ready file is owner-written in Receipts, outside runtime write authority.
 $readyData=Get-Content -LiteralPath $ready -Raw | ConvertFrom-Json
 if($readyData.schema_version -ne 'native-pipe-fixture-ready-v1' -or $readyData.execution_available -ne $false -or $readyData.pipe_name -notmatch '^AgenticRequest-[0-9a-f]{32}$'){throw 'Native fixture handshake invalid.'}
 Enable-LocalUser AgenticPaperRuntime
 $client=Start-Process -FilePath "$env:WINDIR\System32\WindowsPowerShell\v1.0\powershell.exe" -Credential $credential -WorkingDirectory $root -WindowStyle Hidden -PassThru -RedirectStandardOutput (Join-Path (Join-Path $root 'Logs') "native-client-stdout-$id.txt") -RedirectStandardError (Join-Path (Join-Path $root 'Logs') "native-client-stderr-$id.txt") -ArgumentList @('-NoProfile','-NonInteractive','-ExecutionPolicy','Bypass','-File',"`"$childPath`"",'-PipeName',$readyData.pipe_name,'-RequestId',$requestId)
 $clientHandle=$client.Handle
 if($clientHandle -eq [IntPtr]::Zero){throw 'Native client handle unavailable.'}
 [IO.File]::WriteAllText(($gate+'.tmp'),'OWNER_NATIVE_FIXTURE_READY')
 [IO.File]::Move(($gate+'.tmp'),$gate)
 if(-not $client.WaitForExit(10000)){throw 'Native client timed out.'}
 $client.WaitForExit()
 if($null -eq $client.ExitCode -or $client.ExitCode -ne 0){throw "Native client failed; inspect native-client-stderr-$id.txt in Logs."}
 if(-not $server.WaitForExit(10000)){throw 'Native server timed out.'}
 $server.WaitForExit()
 if($null -eq $server.ExitCode -or $server.ExitCode -ne 0){throw "Native server failed; inspect native-server-stderr-$id.txt in Logs."}
}finally{
 try{foreach($process in @($client,$server)){if($process -and -not $process.HasExited){$process.Kill();$process.WaitForExit(5000) | Out-Null}}}
 finally{Disable-LocalUser AgenticPaperRuntime -ErrorAction Stop}
}
if((Get-LocalUser AgenticPaperRuntime).Enabled){throw 'Runtime disabling verification failed.'}
if((Get-FileHash -LiteralPath $childPath -Algorithm SHA256).Hash -ne $childHash){throw 'Fixture client code changed.'}
$result=Get-Content -LiteralPath $report -Raw | ConvertFrom-Json
if($result.schema_version -ne 'runtime-native-pipe-fixture-v1' -or $result.scope -ne 'SYNTHETIC_NATIVE_OWNER_RUNTIME_PIPE_ONLY' -or $result.registration.observed_caller_role -ne 'RUNTIME' -or $result.registration.request_id -ne $requestId -or -not $result.registration.request_registered -or $result.journal.retained_requests -ne 1){throw 'Native fixture identity/journal result mismatch.'}
foreach($part in @($result,$result.registration,$result.journal)){if($part.execution_available -ne $false -or $part.reset_performed -ne $false){throw 'Unexpected native fixture authority.'}}
if($result.registration.controller_admitted -ne $false -or $result.owner_approval_verified -ne $false -or $result.trial_started -ne $false -or $result.service_deployed -ne $false){throw 'Unexpected native fixture activation.'}
Write-Output "Native runtime pipe registration fixture passed. Account disabled again. Evidence: $report"
Write-Output 'Synthetic request only; remote-host denial, protected service deployment, passkey approval, provider guarantees and reset remain unqualified.'
