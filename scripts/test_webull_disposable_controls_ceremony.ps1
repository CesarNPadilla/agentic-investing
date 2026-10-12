# Disposable controls review: real owner passkey, synthetic account/plan, bounded guardian.
[CmdletBinding()]
param([switch]$PrepareOnly)
$ErrorActionPreference='Stop'
$owner=[Security.Principal.WindowsIdentity]::GetCurrent()
if(-not [Environment]::Is64BitProcess -or -not ([Security.Principal.WindowsPrincipal]::new($owner)).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)){throw 'Elevated 64-bit owner required.'}
$guardian=Get-LocalUser AgenticGuardian
if($guardian.Enabled -or (Get-LocalUser AgenticPaperRuntime).Enabled){throw 'Both accounts must start disabled.'}
$pin='9982aad73ea736f2853accd4d209f812212d5a7d08b8270a4e2fbec54a64526b'
$audit=& (Join-Path $PSScriptRoot 'audit_webull_guardian_release.ps1') -ExpectedManifestSha256 $pin | ConvertFrom-Json
$python=Join-Path $audit.installed_directory 'python.exe'
$driver=Join-Path $audit.installed_directory 'app\scripts\webull_disposable_controls_ceremony.py'
$root='C:\ProgramData\AgenticInvestingGuardian'
$id=[guid]::NewGuid().ToString('N')
$admin=[Security.Principal.SecurityIdentifier]::new('S-1-5-32-544')
$system=[Security.Principal.SecurityIdentifier]::new('S-1-5-18')
function Rules($Acl){@($Acl.GetAccessRules($true,$true,[Security.Principal.SecurityIdentifier]) | ForEach-Object {'{0}|{1}|{2}|{3}|{4}|{5}' -f $_.IdentityReference.Value,[int]$_.FileSystemRights,[int]$_.InheritanceFlags,[int]$_.PropagationFlags,[int]$_.AccessControlType,$_.IsInherited} | Sort-Object)}
function Write-Protected([string]$Path,[byte[]]$Bytes){
 $stream=[IO.File]::Open($Path,[IO.FileMode]::CreateNew,[IO.FileAccess]::Write)
 try{$stream.Write($Bytes,0,$Bytes.Length);$stream.Flush($true)}finally{$stream.Dispose()}
 $acl=[Security.AccessControl.FileSecurity]::new();$acl.SetOwner($admin);$acl.SetAccessRuleProtection($true,$false)
 foreach($sid in @($admin,$system,$owner.User,$guardian.SID)){
  $rights=if($sid -eq $admin -or $sid -eq $system){'FullControl'}else{'ReadAndExecute'}
  $acl.AddAccessRule([Security.AccessControl.FileSystemAccessRule]::new($sid,$rights,'Allow'))
 }
 Set-Acl -LiteralPath $Path -AclObject $acl
 $actual=Get-Acl -LiteralPath $Path
 if(-not $actual.AreAccessRulesProtected -or $actual.GetOwner([Security.Principal.SecurityIdentifier]) -ne $admin -or (Compare-Object (Rules $acl) (Rules $actual)) -or ((Get-Item -LiteralPath $Path).Attributes -band [IO.FileAttributes]::ReparsePoint)){throw 'Protected fixture file check failed.'}
}
$materialStart=[Diagnostics.ProcessStartInfo]::new()
$materialStart.FileName=$python;$materialStart.Arguments='-I -B "'+$driver+'" material '+$owner.User.Value+' '+$guardian.SID.Value+' '+$pin

$materialStart.UseShellExecute=$false;$materialStart.CreateNoWindow=$true;$materialStart.RedirectStandardError=$true;$materialStart.RedirectStandardOutput=$true
$materialProcess=[Diagnostics.Process]::Start($materialStart);$null=$materialProcess.Handle
$materialOutput=$materialProcess.StandardOutput.ReadToEndAsync();$materialError=$materialProcess.StandardError.ReadToEndAsync()
try{
 if(-not $materialProcess.WaitForExit(10000)){$materialProcess.Kill();throw 'Synthetic material preparation timeout.'}
 $materialProcess.WaitForExit()
 if($materialProcess.ExitCode -ne 0 -or $materialError.Result.Length -ne 0){throw 'Synthetic material preparation failed.'}
 $material=[Text.Encoding]::UTF8.GetString([Convert]::FromBase64String($materialOutput.Result.Trim())) | ConvertFrom-Json
}finally{$materialProcess.Dispose()}
if($material.purpose -cne 'WEBULL_DISPOSABLE_CONTROLS_TEST_ONLY'){throw 'Authentication diagnostic scope required.'}
$configurationPath=Join-Path $root "Code\HostConfig-$id.json"
Write-Protected $configurationPath ([Text.Encoding]::UTF8.GetBytes(($material.configuration | ConvertTo-Json -Depth 20 -Compress)))
$configurationHash=(Get-FileHash -LiteralPath $configurationPath).Hash.ToLowerInvariant()
$layoutReceipt=@(& (Join-Path $PSScriptRoot 'prepare_webull_review_layout.ps1') -ConfigurationPath $configurationPath -ExpectedConfigurationSha256 $configurationHash -SyntheticOnly -ExpectedManifestSha256 $pin)
if($layoutReceipt.Count -ne 1){throw 'One layout receipt required.'}
$layout=Get-Content -LiteralPath $layoutReceipt[0] -Raw | ConvertFrom-Json
$ownerDirectory=Split-Path $layout.journal_path -Parent


$journalHash=(Get-FileHash -LiteralPath $layout.journal_path).Hash.ToLowerInvariant()
$bootstrap=Join-Path $root "Code\ControlsOwnerBootstrap-$id.py"
$c=@{driver=$driver;owner=$owner.User.Value;guardian=$guardian.SID.Value;manifest=$pin;configuration=$configurationPath;hash=$configurationHash;id=$id;stdout=(Join-Path $ownerDirectory 'owner-stdout.txt');stderr=(Join-Path $ownerDirectory 'owner-stderr.txt')} | ConvertTo-Json -Compress
$code=@('import runpy,sys',('c='+$c),"sys.stdout=open(c['stdout'],'x',encoding='utf-8')","sys.stderr=open(c['stderr'],'x',encoding='utf-8')","sys.argv=[c['driver'],'owner',c['owner'],c['guardian'],c['manifest'],c['configuration'],c['hash'],c['id']]","runpy.run_path(c['driver'],run_name='__main__')") -join [Environment]::NewLine
Write-Protected $bootstrap ([Text.Encoding]::UTF8.GetBytes($code))
& $python -I -B -c 'import pathlib,sys;compile(pathlib.Path(sys.argv[1]).read_bytes(),sys.argv[1],sys.argv[2])' $bootstrap exec
if($LASTEXITCODE -ne 0){throw 'Controls owner bootstrap compilation failed.'}
$arguments='-I -B "'+$driver+'" supervisor '+$owner.User.Value+' '+$guardian.SID.Value+' '+$pin+' "'+$configurationPath+'" '+$configurationHash+' '+$id
if($python.Length+3+$arguments.Length -ge 1024){throw 'Credentialed command too long.'}
if($PrepareOnly){
 [ordered]@{schema_version='disposable-controls-ceremony-preparation-v1';purpose='WEBULL_DISPOSABLE_CONTROLS_TEST_ONLY';fixture_id=$id;configuration_path=$configurationPath;configuration_sha256=$configurationHash;bootstrap_path=$bootstrap;bootstrap_sha256=(Get-FileHash -LiteralPath $bootstrap).Hash.ToLowerInvariant();layout_receipt_path=$layoutReceipt[0];manifest_sha256=$pin;guardian_disabled=$true;runtime_disabled=$true;listener_started=$false;credential_prompted=$false;passkey_used=$false;trial_started=$false} | ConvertTo-Json
 return
}
. (Join-Path $PSScriptRoot 'webull_standard_owner_process.ps1')
$launcher=New-StandardOwnerLauncher
$password=Read-Host 'Enter AgenticGuardian password locally (do not share it)' -AsSecureString
$start=[Diagnostics.ProcessStartInfo]::new();$start.FileName=$python;$start.Arguments=$arguments
$start.WorkingDirectory=Join-Path $root 'Logs';$start.UseShellExecute=$false;$start.CreateNoWindow=$true;$start.LoadUserProfile=$false
$start.UserName='AgenticGuardian';$start.Domain=$env:COMPUTERNAME;$start.Password=$password
$start.RedirectStandardError=$true;$start.RedirectStandardOutput=$true;$start.EnvironmentVariables.Clear()
foreach($name in @('SystemRoot','WINDIR')){$start.EnvironmentVariables[$name]=$env:WINDIR}
$start.EnvironmentVariables['PATH']=Join-Path $env:WINDIR 'System32'
foreach($name in @('TEMP','TMP')){$start.EnvironmentVariables[$name]=Join-Path $root 'Logs'}
$process=$null;$stdout=$null;$stderr=$null
try{
 Enable-LocalUser AgenticGuardian
 $process=[Diagnostics.Process]::Start($start);$null=$process.Handle
 $stdout=$process.StandardOutput.ReadToEndAsync();$stderr=$process.StandardError.ReadToEndAsync()
 $watch=[Diagnostics.Stopwatch]::StartNew();$waiting=Join-Path $root "Logs\controls-ready-$id-waiting.json"
 while(-not (Test-Path -LiteralPath $waiting)){
  if($process.HasExited -or $watch.ElapsedMilliseconds -gt 8000){throw 'Guardian readiness unavailable; retain evidence.'}
  Start-Sleep -Milliseconds 20
 }
 Write-Host 'Open http://localhost:8767 yourself now. Confirm SYNTHETIC ACCOUNT AND PLAN, then select Sign this disposable test with Windows Hello / passkey.'
 Write-Host 'Complete within 40 seconds. This signs disposable test evidence only; no real account, reset, order or trial approval.'
 $variables=@{SystemRoot=$env:WINDIR;WINDIR=$env:WINDIR;PATH=(Join-Path $env:WINDIR 'System32');TEMP=$ownerDirectory;TMP=$ownerDirectory}
 $environment=(@($variables.Keys | Sort-Object | ForEach-Object {$_+'='+$variables[$_]}) -join [char]0)+[char]0+[char]0
 $ownerExit=$launcher::Run($python,('"'+$python+'" -I -B "'+$bootstrap+'"'),$environment,$ownerDirectory)
 if($ownerExit -ne 0){throw "Disposable controls ceremony failed/expired; diagnostics: $ownerDirectory\owner-stderr.txt"}
 if(-not $process.WaitForExit(20000)){throw 'Guardian supervisor outer wait exceeded.'}
 $process.WaitForExit()
 if($process.ExitCode -ne 0){throw 'Guardian controls host failed; retained evidence requires review.'}
}finally{
 try{if($process){if(-not $process.HasExited){$process.Kill();$null=$process.WaitForExit(5000)}
  if($process.HasExited){[IO.File]::WriteAllText((Join-Path $root "Logs\controls-stderr-$id.txt"),$stderr.Result);[IO.File]::WriteAllText((Join-Path $root "Logs\controls-stdout-$id.txt"),$stdout.Result)}
 }}finally{Disable-LocalUser AgenticGuardian -ErrorAction Stop;$password.Dispose()}
}
$hostPath=Join-Path $root "Receipts\controls-host-$id.json"
$supervisorPath=Join-Path $root "Receipts\controls-supervisor-$id.json"
$ownerResultPath=Join-Path $ownerDirectory 'controls-owner-result.json'
$hostResult=Get-Content -LiteralPath $hostPath -Raw | ConvertFrom-Json
$supervisor=Get-Content -LiteralPath $supervisorPath -Raw | ConvertFrom-Json
$ownerResult=Get-Content -LiteralPath $ownerResultPath -Raw | ConvertFrom-Json
if($hostResult.state -cne 'REVIEW_RETAINED_HOST_CLOSED_NO_RESET_AUTHORITY' -or $hostResult.disposable_controls_test_only -ne $true -or $ownerResult.disposable_controls_test_only -ne $true -or $ownerResult.real_owner_passkey_used -ne $true -or $ownerResult.http_listener_closed -ne $true -or $ownerResult.guardian_reference_confirmed -ne $true -or $ownerResult.standard_owner_process_verified -ne $true -or $supervisor.process_tree_active -ne 0 -or $supervisor.exit_code -ne 0){throw 'Integrated controls result mismatch.'}
foreach($record in @($hostResult,$ownerResult,$supervisor)){
 foreach($flag in @('reset_authorized','execution_available')){if($record.$flag -isnot [bool] -or $record.$flag -ne $false){throw 'Controls scope mismatch.'}}
}
foreach($record in @($ownerResult,$supervisor)){if($record.trial_started -isnot [bool] -or $record.trial_started -ne $false){throw 'Trial scope mismatch.'}}
if($hostResult.probe_id -cne $id -or $ownerResult.probe_id -cne $id){throw 'Ceremony identity mismatch.'}
foreach($log in @((Join-Path $ownerDirectory 'owner-stderr.txt'),(Join-Path $root "Logs\controls-stderr-$id.txt"))){if((Get-Item -LiteralPath $log).Length -ne 0){throw 'Controls diagnostics nonempty.'}}
if((Get-LocalUser AgenticGuardian).Enabled -or (Get-LocalUser AgenticPaperRuntime).Enabled){throw 'Accounts must finish disabled.'}
$null=& (Join-Path $PSScriptRoot 'audit_webull_guardian_release.ps1') -ExpectedManifestSha256 $pin
$links=[ordered]@{}
foreach($path in @($PSCommandPath,$configurationPath,$bootstrap,$layoutReceipt[0],$hostPath,$supervisorPath,$ownerResultPath,$layout.journal_path,(Join-Path $root 'Code\AcceptedOwnerCredential-9fe4cf37ee9513eb9668dc2de0997b117abe83704ef0cc79a1c27e38b046b778.json'),(Join-Path $PSScriptRoot 'webull_standard_owner_process.ps1'))){$links[$path]=(Get-FileHash -LiteralPath $path).Hash.ToLowerInvariant()}
$wrapper=Join-Path $root "Receipts\disposable-controls-wrapper-$id.json"
$value=[ordered]@{schema_version='disposable-controls-wrapper-v1';purpose='WEBULL_DISPOSABLE_CONTROLS_TEST_ONLY';fixture_id=$id;manifest_sha256=$pin;configuration_path=$configurationPath;owner_result_path=$ownerResultPath;host_result_path=$hostPath;supervisor_result_path=$supervisorPath;retained_hash_links=$links;real_owner_passkey_used=$true;synthetic_account_and_plan_context_only=$true;guardian_disabled=$true;runtime_disabled=$true;service_deployed=$false;reset_authorized=$false;execution_available=$false;trial_started=$false}
$stream=[IO.File]::Open($wrapper,[IO.FileMode]::CreateNew,[IO.FileAccess]::Write)
try{$bytes=[Text.Encoding]::UTF8.GetBytes(($value | ConvertTo-Json -Depth 8));$stream.Write($bytes,0,$bytes.Length);$stream.Flush($true)}finally{$stream.Dispose()}
Write-Output "Disposable passkey/guardian controls ceremony passed. Both accounts disabled. Evidence: $wrapper"
Write-Output 'Test evidence only; real account/provider evidence, protected rollback/revocation, reset and trading remain unqualified.'
