# Generated-signature fixture across real standard-owner/guardian tokens; no broker/reset.
[CmdletBinding()]
param([switch]$PrepareOnly)
$ErrorActionPreference='Stop'
$owner=[Security.Principal.WindowsIdentity]::GetCurrent()
if(-not [Environment]::Is64BitProcess -or -not ([Security.Principal.WindowsPrincipal]::new($owner)).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)){throw 'Elevated 64-bit owner required.'}
$guardian=Get-LocalUser AgenticGuardian
if($guardian.Enabled -or (Get-LocalUser AgenticPaperRuntime).Enabled){throw 'Both accounts must start disabled.'}
$pin='800ab34b3c240536017d8fc3fa8fcdb93e169fbacc47ef7f9933936f41d4c6ae'
$audit=& (Join-Path $PSScriptRoot 'audit_webull_guardian_release.ps1') -ExpectedManifestSha256 $pin | ConvertFrom-Json
$python=Join-Path $audit.installed_directory 'python.exe'
$driver=Join-Path $audit.installed_directory 'app\scripts\webull_signed_host_fixture.py'
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
if($material.synthetic_key_only -ne $true){throw 'Synthetic fixture scope required.'}
$configurationPath=Join-Path $root "Code\HostConfig-$id.json"
$signedPath=Join-Path $root "Code\SignedReceipt-$id.json"
Write-Protected $configurationPath ([Text.Encoding]::UTF8.GetBytes(($material.configuration | ConvertTo-Json -Depth 20 -Compress)))
Write-Protected $signedPath ([Text.Encoding]::UTF8.GetBytes(($material.signed_receipt | ConvertTo-Json -Depth 20 -Compress)))
$configurationHash=(Get-FileHash -LiteralPath $configurationPath).Hash.ToLowerInvariant()
$signedHash=(Get-FileHash -LiteralPath $signedPath).Hash.ToLowerInvariant()
$layoutReceipt=@(& (Join-Path $PSScriptRoot 'prepare_webull_review_layout.ps1') -ConfigurationPath $configurationPath -ExpectedConfigurationSha256 $configurationHash -SyntheticOnly -ExpectedManifestSha256 $pin)
if($layoutReceipt.Count -ne 1){throw 'One layout receipt required.'}
$layout=Get-Content -LiteralPath $layoutReceipt[0] -Raw | ConvertFrom-Json
$ownerDirectory=Split-Path $layout.journal_path -Parent
$bootstrap=Join-Path $root "Code\SignedOwnerBootstrap-$id.py"
$c=@{driver=$driver;owner=$owner.User.Value;guardian=$guardian.SID.Value;manifest=$pin;configuration=$configurationPath;hash=$configurationHash;id=$id;signed=$signedPath;stdout=(Join-Path $ownerDirectory 'owner-stdout.txt');stderr=(Join-Path $ownerDirectory 'owner-stderr.txt')} | ConvertTo-Json -Compress
$code=@('import runpy,sys',('c='+$c),"sys.stdout=open(c['stdout'],'x',encoding='utf-8')","sys.stderr=open(c['stderr'],'x',encoding='utf-8')","sys.argv=[c['driver'],'owner',c['owner'],c['guardian'],c['manifest'],c['configuration'],c['hash'],c['id'],c['signed']]","runpy.run_path(c['driver'],run_name='__main__')") -join [Environment]::NewLine
Write-Protected $bootstrap ([Text.Encoding]::UTF8.GetBytes($code))
$arguments='-I -B "'+$driver+'" supervisor '+$owner.User.Value+' '+$guardian.SID.Value+' '+$pin+' "'+$configurationPath+'" '+$configurationHash+' '+$id+' "'+$signedPath+'"'
$length=$python.Length+3+$arguments.Length
if($length -ge 1024){throw 'Credentialed launch command exceeds safe bound.'}
if($PrepareOnly){
 [ordered]@{schema_version='signed-host-preparation-v1';fixture_id=$id;configuration_path=$configurationPath;configuration_sha256=$configurationHash;signed_receipt_path=$signedPath;signed_receipt_sha256=$signedHash;bootstrap_path=$bootstrap;bootstrap_sha256=(Get-FileHash -LiteralPath $bootstrap).Hash.ToLowerInvariant();layout_receipt_path=$layoutReceipt[0];credentialed_command_line_characters=$length;synthetic_only=$true;guardian_disabled=$true;runtime_disabled=$true;host_started=$false;trial_started=$false} | ConvertTo-Json
 return
}
. (Join-Path $PSScriptRoot 'webull_standard_owner_process.ps1')
$launcher=New-StandardOwnerLauncher
$password=Read-Host 'Enter AgenticGuardian password locally (do not share it)' -AsSecureString
$start=[Diagnostics.ProcessStartInfo]::new()
$start.FileName=$python;$start.Arguments=$arguments;$start.WorkingDirectory=Join-Path $root 'Logs'
$start.UseShellExecute=$false;$start.CreateNoWindow=$true;$start.LoadUserProfile=$false
$start.UserName='AgenticGuardian';$start.Domain=$env:COMPUTERNAME;$start.Password=$password
$start.RedirectStandardError=$true;$start.RedirectStandardOutput=$true
$start.EnvironmentVariables.Clear()
foreach($name in @('SystemRoot','WINDIR')){$start.EnvironmentVariables[$name]=$env:WINDIR}
$start.EnvironmentVariables['PATH']=Join-Path $env:WINDIR 'System32'
foreach($name in @('TEMP','TMP')){$start.EnvironmentVariables[$name]=Join-Path $root 'Logs'}
$process=$null;$stdout=$null;$stderr=$null
try{
 Enable-LocalUser AgenticGuardian
 $process=[Diagnostics.Process]::Start($start);$null=$process.Handle
 $stdout=$process.StandardOutput.ReadToEndAsync();$stderr=$process.StandardError.ReadToEndAsync()
 $ready=Join-Path $root "Logs\signed-host-ready-$id-prepare.json"
 $watch=[Diagnostics.Stopwatch]::StartNew()
 while(-not (Test-Path -LiteralPath $ready)){
  if($process.HasExited -or $watch.ElapsedMilliseconds -gt 8000){throw 'Signed host discovery unavailable; retain state.'}
  Start-Sleep -Milliseconds 20
 }
 $variables=@{SystemRoot=$env:WINDIR;WINDIR=$env:WINDIR;PATH=(Join-Path $env:WINDIR 'System32');TEMP=$ownerDirectory;TMP=$ownerDirectory}
 $environment=(@($variables.Keys | Sort-Object | ForEach-Object {$_+'='+$variables[$_]}) -join [char]0)+[char]0+[char]0
 $ownerExit=$launcher::Run($python,('"'+$python+'" -I -B "'+$bootstrap+'"'),$environment,$ownerDirectory)
 if($ownerExit -ne 0){throw "Standard owner fixture failed; diagnostics: $ownerDirectory\owner-stderr.txt"}
 if(-not $process.WaitForExit(25000)){throw 'Signed host supervisor exceeded outer wait.'}
 $process.WaitForExit()
 if($process.ExitCode -ne 0){throw 'Guardian signed host failed; diagnostics retained.'}
}finally{
 try{
  if($process){
   if(-not $process.HasExited){$process.Kill();$null=$process.WaitForExit(5000)}
   if($process.HasExited){[IO.File]::WriteAllText((Join-Path $root "Logs\signed-host-stderr-$id.txt"),$stderr.Result);[IO.File]::WriteAllText((Join-Path $root "Logs\signed-host-stdout-$id.txt"),$stdout.Result)}
  }
 }finally{Disable-LocalUser AgenticGuardian -ErrorAction Stop;$password.Dispose()}
}
if((Get-LocalUser AgenticGuardian).Enabled -or (Get-LocalUser AgenticPaperRuntime).Enabled){throw 'Both accounts must end disabled.'}
$resultPath=Join-Path $root "Receipts\signed-host-result-$id.json"
$supervisorPath=Join-Path $root "Receipts\signed-host-supervisor-$id.json"
$ownerResultPath=Join-Path $ownerDirectory 'signed-owner-result.json'
$result=Get-Content -LiteralPath $resultPath -Raw | ConvertFrom-Json
$supervisor=Get-Content -LiteralPath $supervisorPath -Raw | ConvertFrom-Json
$ownerResult=Get-Content -LiteralPath $ownerResultPath -Raw | ConvertFrom-Json
if($result.state -cne 'REVIEW_RETAINED_HOST_CLOSED_NO_RESET_AUTHORITY' -or $result.probe_id -cne $id -or $result.synthetic_key_only -ne $true -or $ownerResult.standard_owner_process_verified -ne $true -or $ownerResult.guardian_reference_confirmed -ne $true -or $ownerResult.synthetic_key_only -ne $true -or $supervisor.process_tree_active -ne 0 -or $supervisor.exit_code -ne 0){throw 'Integrated synthetic result rejected.'}
foreach($record in @($result,$ownerResult,$supervisor)){if($record.reset_authorized -ne $false -or $record.execution_available -ne $false){throw 'Synthetic result authority flags rejected.'}}
foreach($path in @((Join-Path $ownerDirectory 'owner-stderr.txt'),(Join-Path $root "Logs\signed-host-stderr-$id.txt"))){if((Get-Item -LiteralPath $path).Length -ne 0){throw 'Fixture diagnostic stderr not empty.'}}
if((Get-FileHash -LiteralPath $configurationPath).Hash.ToLowerInvariant() -cne $configurationHash -or (Get-FileHash -LiteralPath $signedPath).Hash.ToLowerInvariant() -cne $signedHash){throw 'Protected synthetic inputs changed.'}
& (Join-Path $PSScriptRoot 'audit_webull_guardian_release.ps1') -ExpectedManifestSha256 $pin | Out-Null
$records=@{}
foreach($path in @($configurationPath,$signedPath,$bootstrap,$layoutReceipt[0],$resultPath,$supervisorPath,$ownerResultPath,$PSCommandPath,(Join-Path $PSScriptRoot 'webull_standard_owner_process.ps1'))){$records[$path]=(Get-FileHash -LiteralPath $path).Hash.ToLowerInvariant()}
$record=[ordered]@{schema_version='signed-host-wrapper-v1';fixture_id=$id;manifest_sha256=$pin;configuration_path=$configurationPath;signed_receipt_path=$signedPath;layout_receipt_path=$layoutReceipt[0];host_result_path=$resultPath;owner_result_path=$ownerResultPath;supervisor_result_path=$supervisorPath;bootstrap_path=$bootstrap;retained_hash_links=$records;guardian_disabled=$true;runtime_disabled=$true;synthetic_key_only=$true;real_owner_passkey_used=$false;service_deployed=$false;reset_authorized=$false;execution_available=$false;trial_started=$false}
$recordPath=Join-Path $root "Receipts\signed-host-wrapper-$id.json"
$stream=[IO.File]::Open($recordPath,[IO.FileMode]::CreateNew,[IO.FileAccess]::Write)
try{$bytes=[Text.Encoding]::UTF8.GetBytes(($record | ConvertTo-Json -Depth 6));$stream.Write($bytes,0,$bytes.Length);$stream.Flush($true)}finally{$stream.Dispose()}
Write-Output "Synthetic signed host/standard-owner fixture passed. Account disabled again. Evidence: $recordPath"
Write-Output 'Generated test signature only; real passkey/app/service lifecycle, recovery/reset and trading remain unqualified.'
