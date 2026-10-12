# Owner-run cross-identity pipe fixture. No broker, approval, reset or service deployment.
[CmdletBinding()]
param()
$ErrorActionPreference='Stop'
. (Join-Path $PSScriptRoot 'paper_pipe_fixture_security.ps1')
$identity=[Security.Principal.WindowsIdentity]::GetCurrent()
$principal=New-Object Security.Principal.WindowsPrincipal($identity)
if(-not $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)){throw 'Run in elevated 64-bit Windows PowerShell.'}
$runtime=Get-LocalUser -Name 'AgenticPaperRuntime'
if($runtime.Enabled){throw 'Runtime must start disabled.'}
if($runtime.SID -eq $identity.User){throw 'Distinct owner/runtime identities required.'}
$root='C:\ProgramData\AgenticInvestingPaper'
foreach($area in @('Code','Logs')){
    $acl=Get-Acl -LiteralPath (Join-Path $root $area)
    if(-not $acl.AreAccessRulesProtected -or $acl.GetOwner([Security.Principal.SecurityIdentifier]).Value -ne 'S-1-5-32-544'){throw 'Protected fixture layout required.'}
}
$id=[guid]::NewGuid().ToString('N')
$pipeName="AgenticIdentityFixture-$id"
$childPath=Join-Path (Join-Path $root 'Code') "pipe-client-$id.ps1"
$childText=@'
param([string]$PipeName)
$ErrorActionPreference='Stop'
$rights=[IO.Pipes.PipeAccessRights]::ReadData -bor [IO.Pipes.PipeAccessRights]::WriteData -bor [IO.Pipes.PipeAccessRights]::ReadAttributes -bor [IO.Pipes.PipeAccessRights]::Synchronize
$client=[IO.Pipes.NamedPipeClientStream]::new('.', $PipeName, $rights, [IO.Pipes.PipeOptions]::None, [Security.Principal.TokenImpersonationLevel]::Identification, [IO.HandleInheritability]::None)
try{
    $client.Connect(10000)
    $client.WriteByte(1)
    $client.Flush()
    Start-Sleep -Seconds 3
}finally{$client.Dispose()}
'@
$stream=[IO.File]::Open($childPath,[IO.FileMode]::CreateNew,[IO.FileAccess]::Write)
try{$bytes=[Text.Encoding]::UTF8.GetBytes($childText);$stream.Write($bytes,0,$bytes.Length)}finally{$stream.Dispose()}
$codeHash=(Get-FileHash -LiteralPath $childPath -Algorithm SHA256).Hash
$credential=Get-Credential -UserName "$env:COMPUTERNAME\AgenticPaperRuntime" -Message 'Enter the locally held AgenticPaperRuntime password; do not share it.'
if(-not $credential -or $credential.UserName -ne "$env:COMPUTERNAME\AgenticPaperRuntime"){throw 'Expected local runtime credential required.'}
$pipe=$process=$null
try{
    $security=New-Object IO.Pipes.PipeSecurity
    $security.SetAccessRuleProtection($true,$false)
    $security.SetOwner($identity.User)
    $security.AddAccessRule([IO.Pipes.PipeAccessRule]::new($identity.User,[IO.Pipes.PipeAccessRights]::FullControl,[Security.AccessControl.AccessControlType]::Allow))
    # CreateFile also needs read-attributes; omit instance creation/permission changes.
    $clientRights=[IO.Pipes.PipeAccessRights]::ReadData -bor [IO.Pipes.PipeAccessRights]::WriteData -bor [IO.Pipes.PipeAccessRights]::ReadAttributes -bor [IO.Pipes.PipeAccessRights]::Synchronize
    $security.AddAccessRule([IO.Pipes.PipeAccessRule]::new($runtime.SID,$clientRights,[Security.AccessControl.AccessControlType]::Allow))
    $pipe=[IO.Pipes.NamedPipeServerStream]::new($pipeName,[IO.Pipes.PipeDirection]::InOut,1,[IO.Pipes.PipeTransmissionMode]::Byte,[IO.Pipes.PipeOptions]::Asynchronous,4096,4096,$security,[IO.HandleInheritability]::None,[IO.Pipes.PipeAccessRights]::TakeOwnership)
    # Elevated-server integrity must not implicitly reject the intended medium client.
    # Only this disposable pipe is relabeled; its restrictive DACL remains unchanged.
    $labelEvidence=Set-PaperFixturePipeMediumLabel -Pipe $pipe
    $pending=$pipe.BeginWaitForConnection($null,$null)
    Enable-LocalUser -Name 'AgenticPaperRuntime'
    $stderrPath=Join-Path (Join-Path $root 'Logs') "pipe-stderr-$id.txt"
    [ordered]@{SchemaVersion='runtime-pipe-startup-diagnostic-v1';BeforeLabel=$labelEvidence.Before;AfterLabel=$labelEvidence.After;RuntimeRequestedAccessMask=[int]$clientRights;MediumLabelVerified=$labelEvidence.MediumLabelVerified;ExecutionAvailable=$false;TrialStarted=$false} | ConvertTo-Json | Set-Content -LiteralPath (Join-Path (Join-Path $root 'Logs') "pipe-startup-$id.json") -Encoding utf8
    $process=Start-Process -FilePath "$env:WINDIR\System32\WindowsPowerShell\v1.0\powershell.exe" -Credential $credential -WorkingDirectory $root -WindowStyle Hidden -PassThru -RedirectStandardOutput (Join-Path (Join-Path $root 'Logs') "pipe-stdout-$id.txt") -RedirectStandardError $stderrPath -ArgumentList @('-NoProfile','-NonInteractive','-ExecutionPolicy','Bypass','-File',"`"$childPath`"",'-PipeName',$pipeName)
    $retainedHandle=$process.Handle
    if($retainedHandle -eq [IntPtr]::Zero){throw 'Child process handle unavailable.'}
    $connectTimer=[Diagnostics.Stopwatch]::StartNew()
    while(-not $pending.AsyncWaitHandle.WaitOne(200)){
        if($process.HasExited){$process.WaitForExit();throw "Runtime pipe client exited before connecting (exit $($process.ExitCode)); diagnostic log: $stderrPath"}
        if($connectTimer.ElapsedMilliseconds -ge 15000){throw "Runtime pipe connect timed out; diagnostic log: $stderrPath"}
    }
    $pipe.EndWaitForConnection($pending)
    $buffer=New-Object byte[] 1
    $read=$pipe.ReadAsync($buffer,0,1)
    if(-not $read.Wait(5000) -or $read.Result -ne 1 -or $buffer[0] -ne 1){throw 'Dummy client message unavailable.'}
    $script:observedPipeSid=$null
    $pipe.RunAsClient([IO.Pipes.PipeStreamImpersonationWorker]{ $script:observedPipeSid=[Security.Principal.WindowsIdentity]::GetCurrent().User.Value })
    if($script:observedPipeSid -ne $runtime.SID.Value){throw 'OS pipe client identity mismatch.'}
    if([Security.Principal.WindowsIdentity]::GetCurrent().User.Value -ne $identity.User.Value){throw 'Server identity not restored.'}
    if(-not $process.WaitForExit(10000)){throw 'Runtime pipe client did not exit.'}
    $process.WaitForExit()
    if($null -eq $process.ExitCode -or $process.ExitCode -ne 0){throw 'Runtime pipe client failed or exit code unavailable.'}
}finally{
    try{
        if($pipe){$pipe.Dispose()}
        if($process -and -not $process.HasExited){$process.Kill();$process.WaitForExit(5000) | Out-Null}
    }finally{Disable-LocalUser -Name 'AgenticPaperRuntime' -ErrorAction Stop}
}
if((Get-LocalUser -Name 'AgenticPaperRuntime').Enabled){throw 'Runtime disabling verification failed.'}
if((Get-FileHash -LiteralPath $childPath -Algorithm SHA256).Hash -ne $codeHash){throw 'Dummy client code changed.'}
$reportPath=Join-Path (Join-Path $root 'Logs') "pipe-identity-result-$id.json"
[ordered]@{SchemaVersion='runtime-pipe-identity-fixture-v1';ObservedAtUtc=[DateTime]::UtcNow.ToString('o');OsClientMatchesRuntime=$true;ServerIdentityRestored=$true;RuntimeDisabledAfterTest=$true;ChildExitCode=0;ReviewedChildSha256=$codeHash;MediumPipeLabelVerified=$true;Scope='ELEVATED_OWNER_DOTNET_PIPE_FIXTURE_ONLY';NativePythonCrossIdentityQualified=$false;RemoteClientDenialQualified=$false;ControllerAdmitted=$false;ResetPerformed=$false;ExecutionAvailable=$false;TrialStarted=$false} | ConvertTo-Json | Set-Content -LiteralPath $reportPath -Encoding utf8
Write-Output "Runtime pipe identity fixture passed. Account disabled again. Evidence: $reportPath"
Write-Output 'No service deployed; remote-client denial, native cross-identity controller transport, passkey approval and reset remain unqualified.'
