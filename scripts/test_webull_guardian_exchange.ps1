# Elevated owner-run synthetic guardian reply fixture. No review state or broker calls.
[CmdletBinding()]
param([switch]$PrepareOnly,[switch]$StandardOwnerClient)
$ErrorActionPreference='Stop'
$identity=[Security.Principal.WindowsIdentity]::GetCurrent()
if(-not [Environment]::Is64BitProcess -or -not ([Security.Principal.WindowsPrincipal]::new($identity)).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)){throw 'Elevated 64-bit owner PowerShell required.'}
$guardian=Get-LocalUser AgenticGuardian
if($guardian.Enabled -or (Get-LocalUser AgenticPaperRuntime).Enabled){throw 'Both accounts must start disabled.'}
$pin='2cb10942c251ffec2976168ff56661181845dd2e72d0ef724a4efe32210cbad6'
$audit=& (Join-Path $PSScriptRoot 'audit_webull_guardian_release.ps1') -ExpectedManifestSha256 $pin | ConvertFrom-Json
$release=$audit.installed_directory
$root='C:\ProgramData\AgenticInvestingGuardian'
$parent=Join-Path $root 'Code'
$admin=[Security.Principal.SecurityIdentifier]::new('S-1-5-32-544')
$system=[Security.Principal.SecurityIdentifier]::new('S-1-5-18')
$parentAcl=Get-Acl -LiteralPath $parent
if(-not $parentAcl.AreAccessRulesProtected -or $parentAcl.GetOwner([Security.Principal.SecurityIdentifier]) -ne $admin){throw 'Protected Code parent required.'}
if((Get-Item -LiteralPath $parent).Attributes -band [IO.FileAttributes]::ReparsePoint){throw 'Ordinary Code parent required.'}
$id=[guid]::NewGuid().ToString()
$fixture=Join-Path $parent ('ExchangeFixture-'+$id)
$ready=Join-Path $root "Logs\exchange-ready-$id.json"
$receipt=Join-Path $root "Receipts\exchange-result-$id.json"
function Rules($Acl){@($Acl.GetAccessRules($true,$true,[Security.Principal.SecurityIdentifier]) | ForEach-Object {'{0}|{1}|{2}|{3}|{4}|{5}' -f $_.IdentityReference.Value,[int]$_.FileSystemRights,[int]$_.InheritanceFlags,[int]$_.PropagationFlags,[int]$_.AccessControlType,$_.IsInherited} | Sort-Object)}
function Protect-New([string]$Path,[bool]$Directory){
 if($Directory){$acl=[Security.AccessControl.DirectorySecurity]::new()}else{$acl=[Security.AccessControl.FileSecurity]::new()}
 $acl.SetOwner($admin);$acl.SetAccessRuleProtection($true,$false)
 foreach($sid in @($admin,$system,$identity.User,$guardian.SID)){
  $rights=if($sid -eq $admin -or $sid -eq $system){'FullControl'}else{'ReadAndExecute'}
  $inherit=if($Directory){'ContainerInherit,ObjectInherit'}else{'None'}
  $acl.AddAccessRule([Security.AccessControl.FileSystemAccessRule]::new($sid,$rights,$inherit,'None','Allow'))
 }
 Set-Acl -LiteralPath $Path -AclObject $acl
 $actual=Get-Acl -LiteralPath $Path
 if(-not $actual.AreAccessRulesProtected -or $actual.GetOwner([Security.Principal.SecurityIdentifier]) -ne $admin -or (Compare-Object (Rules $acl) (Rules $actual))){throw 'Fixture exact ACL readback failed.'}
}
if(Test-Path -LiteralPath $fixture){throw 'New fixture directory required.'}
New-Item -ItemType Directory -Path $fixture | Out-Null
Protect-New $fixture $true
New-Item -ItemType Directory -Path (Join-Path $fixture 'security') | Out-Null
Protect-New (Join-Path $fixture 'security') $true
$repo=Split-Path $PSScriptRoot -Parent
$sources=@{
 'probe_webull_guardian_exchange.py'=(Join-Path $PSScriptRoot 'probe_webull_guardian_exchange.py')
 'security\windows_guardian_exchange_pipe.py'=(Join-Path $repo 'security\windows_guardian_exchange_pipe.py')
 'security\windows_guardian_exchange_client.py'=(Join-Path $repo 'security\windows_guardian_exchange_client.py')
}
$pinned=@{
 'probe_webull_guardian_exchange.py'='8259bb266f3f2dd2a6d313d5a0240347171631b4072788cf50c878e96f837fd3'
 'security\windows_guardian_exchange_pipe.py'='34d5b29975ad1d03e1ebd7ca2dafaef15559f6b5a651caf5f52d53088f71df72'
 'security\windows_guardian_exchange_client.py'='2836c66c9c12f83908a86163e50e60f7e284ac4b0fc12ab231033fbe9425e412'
}
$hashes=@{};$descriptors=@{}
foreach($name in $sources.Keys){
 $source=$sources[$name]
 # Synced source files may carry OneDrive reparse metadata. Trust only these
 # pinned bytes; never copy the source file object or its reparse metadata.
 $bytes=[IO.File]::ReadAllBytes($source)
 if($bytes.Length -lt 1 -or $bytes.Length -gt 1000000){throw 'Source snapshot size rejected.'}
 $digest=[Security.Cryptography.SHA256]::Create()
 try{$observed=([BitConverter]::ToString($digest.ComputeHash($bytes))).Replace('-','').ToLowerInvariant()}finally{$digest.Dispose()}
 $expected=$pinned[$name]
 if($observed -cne $expected){throw "Pinned source bytes changed: $name"}
 $target=Join-Path $fixture $name
 $stream=[IO.File]::Open($target,[IO.FileMode]::CreateNew,[IO.FileAccess]::Write)
 try{$stream.Write($bytes,0,$bytes.Length);$stream.Flush($true)}finally{$stream.Dispose()}
 Protect-New $target $false
 if((Get-Item -LiteralPath $target).Attributes -band [IO.FileAttributes]::ReparsePoint){throw 'Installed fixture must be an ordinary file.'}
 if((Get-FileHash -LiteralPath $target -Algorithm SHA256).Hash.ToLowerInvariant() -cne $expected){throw 'Fixture source copy mismatch.'}
 $hashes[$name]=$expected;$descriptors[$name]=(Get-Acl -LiteralPath $target).Sddl
}
if($PrepareOnly){
 [ordered]@{schema_version='guardian-exchange-source-snapshot-v1';fixture_directory=$fixture;source_digests=$hashes;ordinary_protected_files_verified=3;guardian_disabled=$true;runtime_disabled=$true;credential_prompted=$false;pipe_started=$false;execution_available=$false;reset_authorized=$false;trial_started=$false} | ConvertTo-Json -Depth 6
 return
}
$standardDirectory=$null;$standardLauncher=$null
if($StandardOwnerClient){
 . (Join-Path $PSScriptRoot 'webull_standard_owner_process.ps1')
 $standardLauncher=New-StandardOwnerLauncher
 $standardDirectory=Join-Path $env:LOCALAPPDATA "AgenticInvesting\staging\guardian-standard-exchange-$id"
 New-Item -ItemType Directory -Path $standardDirectory | Out-Null
 $config=@{probe=(Join-Path $fixture 'probe_webull_guardian_exchange.py');stdout=(Join-Path $standardDirectory 'stdout.txt');stderr=(Join-Path $standardDirectory 'stderr.txt');guardian=$guardian.SID.Value;owner=$identity.User.Value;id=$id} | ConvertTo-Json -Compress
 $literal=ConvertTo-Json -InputObject $config -Compress
 $bootstrap=Join-Path $standardDirectory 'bootstrap.py'
 $code="import json,runpy,sys`nc=json.loads($literal)`nsys.stdout=open(c['stdout'],'x',encoding='utf-8')`nsys.stderr=open(c['stderr'],'x',encoding='utf-8')`nsys.argv=[c['probe'],'client','--guardian-sid',c['guardian'],'--owner-sid',c['owner'],'--id',c['id'],'--standard-owner']`nrunpy.run_path(c['probe'],run_name='__main__')`n"
 [IO.File]::WriteAllText($bootstrap,$code,[Text.UTF8Encoding]::new($false))
 $vars=@{SystemRoot=$env:WINDIR;WINDIR=$env:WINDIR;PATH=(Join-Path $env:WINDIR 'System32');TEMP=$standardDirectory;TMP=$standardDirectory}
 $standardEnvironment=(@($vars.Keys | Sort-Object | ForEach-Object {$_+'='+$vars[$_]}) -join [char]0)+[char]0+[char]0
}
$password=Read-Host 'Enter AgenticGuardian password locally (do not share it)' -AsSecureString
function Start-Info([string]$Mode){
 $start=[Diagnostics.ProcessStartInfo]::new()
 $start.FileName=Join-Path $release 'python.exe'
 $start.Arguments='-I -B "'+(Join-Path $fixture 'probe_webull_guardian_exchange.py')+'" '+$Mode+' --guardian-sid '+$guardian.SID.Value+' --owner-sid '+$identity.User.Value+' --id '+$id
 $start.WorkingDirectory=$fixture;$start.UseShellExecute=$false;$start.CreateNoWindow=$true;$start.LoadUserProfile=$false
 $start.RedirectStandardError=$true;$start.RedirectStandardOutput=$true
 $start.EnvironmentVariables.Clear()
 foreach($name in @('SystemRoot','WINDIR')){$start.EnvironmentVariables[$name]=$env:WINDIR}
 $start.EnvironmentVariables['PATH']=Join-Path $env:WINDIR 'System32'
 foreach($name in @('TEMP','TMP')){$start.EnvironmentVariables[$name]=Join-Path $root 'Logs'}
 if($Mode -eq 'server'){$start.UserName='AgenticGuardian';$start.Domain=$env:COMPUTERNAME;$start.Password=$password}
 return $start
}
$server=$null;$client=$null
try{
 Enable-LocalUser AgenticGuardian
 $server=[Diagnostics.Process]::Start((Start-Info 'server'));$null=$server.Handle
 $deadline=[DateTime]::UtcNow.AddSeconds(15)
 while(-not (Test-Path -LiteralPath $ready)){
  if($server.HasExited -or [DateTime]::UtcNow -ge $deadline){throw 'Guardian exchange startup failed; retained diagnostics.'}
  Start-Sleep -Milliseconds 25
 }
 if($StandardOwnerClient){
  $python=Join-Path $release 'python.exe'
  $standardExit=$standardLauncher::Run($python,('"'+$python+'" -I -B "'+$bootstrap+'"'),$standardEnvironment,$standardDirectory)
  if($standardExit -ne 0){throw "Standard-owner exchange failed (exit $standardExit); retained diagnostics: $standardDirectory\stderr.txt"}
 }else{
  $client=[Diagnostics.Process]::Start((Start-Info 'client'));$null=$client.Handle
  if(-not $client.WaitForExit(8000)){throw 'Owner exchange client exceeded bounded wait.'}
  $client.WaitForExit()
 }
 if(-not $server.WaitForExit(8000)){throw 'Guardian exchange server exceeded bounded wait.'}
 $server.WaitForExit()
 if($null -eq $server.ExitCode -or $server.ExitCode -ne 0 -or (-not $StandardOwnerClient -and ($null -eq $client.ExitCode -or $client.ExitCode -ne 0))){throw 'Cross-account exchange failed; retain diagnostics.'}
}finally{
 try{
  if($StandardOwnerClient){
   foreach($streamName in @('stdout','stderr')){
    $path=Join-Path $standardDirectory "$streamName.txt"
    if(Test-Path -LiteralPath $path){[IO.File]::WriteAllText((Join-Path $root "Logs\exchange-client-$streamName-$id.txt"),[IO.File]::ReadAllText($path))}
   }
  }
  foreach($pair in @(@('server',$server),@('client',$client))){
   if($pair[1]){
    $process=$pair[1]
    if(-not $process.HasExited){$process.Kill();$null=$process.WaitForExit(5000)}
    if($process.HasExited){
     [IO.File]::WriteAllText((Join-Path $root "Logs\exchange-$($pair[0])-stderr-$id.txt"),$process.StandardError.ReadToEnd())
     [IO.File]::WriteAllText((Join-Path $root "Logs\exchange-$($pair[0])-stdout-$id.txt"),$process.StandardOutput.ReadToEnd())
    }
   }
  }
 }finally{Disable-LocalUser AgenticGuardian -ErrorAction Stop;$password.Dispose()}
}
if((Get-LocalUser AgenticGuardian).Enabled -or (Get-LocalUser AgenticPaperRuntime).Enabled){throw 'Accounts must be disabled.'}
foreach($name in $sources.Keys){$target=Join-Path $fixture $name;if((Get-FileHash -LiteralPath $target -Algorithm SHA256).Hash.ToLowerInvariant() -cne $hashes[$name] -or (Get-Acl -LiteralPath $target).Sddl -cne $descriptors[$name]){throw 'Fixture source or descriptor changed.'}}
foreach($mode in @('server','client')){if((Get-Item -LiteralPath (Join-Path $root "Logs\exchange-$mode-stderr-$id.txt")).Length -ne 0){throw 'Diagnostic stderr is not empty.'}}
if((Get-Content -LiteralPath (Join-Path $root "Logs\exchange-client-stdout-$id.txt") -Raw).Trim() -cne 'AUTHENTICATED_GUARDIAN_REPLY_RECEIVED_SYNTHETIC_ONLY'){throw 'Owner client receipt check failed.'}
$result=Get-Content -LiteralPath $receipt -Raw | ConvertFrom-Json
if($result.probe_id -cne $id -or $result.synthetic_request_only -ne $true -or $result.owner_pipe_identity_observed -ne $true -or $result.guardian_reply_receipt_verified -ne $true -or $result.execution_available -ne $false -or $result.reset_authorized -ne $false -or $result.trial_started -ne $false){throw 'Synthetic receipt scope failed.'}
& (Join-Path $PSScriptRoot 'audit_webull_guardian_release.ps1') -ExpectedManifestSha256 $pin | Out-Null
$summary=[ordered]@{schema_version='guardian-exchange-fixture-v1';probe_id=$id;source_digests=$hashes;receipt_sha256=(Get-FileHash -LiteralPath $receipt -Algorithm SHA256).Hash.ToLowerInvariant();wrapper_sha256=(Get-FileHash -LiteralPath $PSCommandPath -Algorithm SHA256).Hash.ToLowerInvariant();guardian_disabled=$true;runtime_disabled=$true;standard_owner_client_qualified=[bool]$StandardOwnerClient;real_reference_used=$false;execution_available=$false;reset_authorized=$false;trial_started=$false}
if($StandardOwnerClient){$summary['standard_launcher_sha256']=(Get-FileHash -LiteralPath (Join-Path $PSScriptRoot 'webull_standard_owner_process.ps1') -Algorithm SHA256).Hash.ToLowerInvariant();$summary['bootstrap_sha256']=(Get-FileHash -LiteralPath $bootstrap -Algorithm SHA256).Hash.ToLowerInvariant();$summary['standard_client_diagnostics']=$standardDirectory}
$summaryPath=Join-Path $root "Receipts\exchange-wrapper-result-$id.json"
$stream=[IO.File]::Open($summaryPath,[IO.FileMode]::CreateNew,[IO.FileAccess]::Write)
try{$bytes=[Text.Encoding]::UTF8.GetBytes(($summary | ConvertTo-Json -Depth 6));$stream.Write($bytes,0,$bytes.Length);$stream.Flush($true)}finally{$stream.Dispose()}
Write-Output "Synthetic guardian reply fixture passed. Account disabled again. Evidence: $summaryPath"
Write-Output "Standard-owner client checked: $([bool]$StandardOwnerClient). Real signing/reference, service lifecycle and reset remain unqualified."
