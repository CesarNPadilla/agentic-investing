# Actual standard-owner pinned app construction; no listener, challenge, guardian launch or broker.
[CmdletBinding()]
param()
$ErrorActionPreference='Stop'
$owner=[Security.Principal.WindowsIdentity]::GetCurrent()
if(-not [Environment]::Is64BitProcess -or -not ([Security.Principal.WindowsPrincipal]::new($owner)).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)){throw 'Elevated 64-bit owner required.'}
$guardian=Get-LocalUser AgenticGuardian
if($guardian.Enabled -or (Get-LocalUser AgenticPaperRuntime).Enabled){throw 'Both accounts must start disabled.'}
$pin='93647e3ddacaff7de9ea18477db5b87a331bb18bdda98c89ca569fe10dda1e38'
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

$journalHash=(Get-FileHash -LiteralPath $layout.journal_path).Hash.ToLowerInvariant()
$probe=Join-Path $audit.installed_directory 'app\scripts\probe_webull_pinned_owner_app.py'
$resultPath=Join-Path $ownerDirectory 'pinned-owner-app-result.json'
$bootstrap=Join-Path $root "Code\PinnedOwnerBootstrap-$id.py"
$c=@{probe=$probe;owner=$owner.User.Value;guardian=$guardian.SID.Value;manifest=$pin;configuration=$configurationPath;hash=$configurationHash;result=$resultPath;stdout=(Join-Path $ownerDirectory 'owner-stdout.txt');stderr=(Join-Path $ownerDirectory 'owner-stderr.txt')} | ConvertTo-Json -Compress
$code=@('import runpy,sys',('c='+$c),"sys.stdout=open(c['stdout'],'x',encoding='utf-8')","sys.stderr=open(c['stderr'],'x',encoding='utf-8')","sys.argv=[c['probe'],c['configuration'],c['hash'],c['manifest'],c['owner'],c['guardian'],c['result']]","runpy.run_path(c['probe'],run_name='__main__')") -join [Environment]::NewLine
Write-Protected $bootstrap ([Text.Encoding]::UTF8.GetBytes($code))
. (Join-Path $PSScriptRoot 'webull_standard_owner_process.ps1')
$launcher=New-StandardOwnerLauncher
$variables=@{SystemRoot=$env:WINDIR;WINDIR=$env:WINDIR;PATH=(Join-Path $env:WINDIR 'System32');TEMP=$ownerDirectory;TMP=$ownerDirectory}
$environment=(@($variables.Keys | Sort-Object | ForEach-Object {$_+'='+$variables[$_]}) -join [char]0)+[char]0+[char]0
$ownerExit=$launcher::Run($python,('"'+$python+'" -I -B "'+$bootstrap+'"'),$environment,$ownerDirectory)
if($ownerExit -ne 0){throw "Standard owner construction failed; retain diagnostics: $ownerDirectory\owner-stderr.txt"}
$result=Get-Content -LiteralPath $resultPath -Raw | ConvertFrom-Json
if($result.standard_owner_process_verified -ne $true -or $result.protected_context_loaded -ne $true -or $result.configuration_sha256 -ne $configurationHash -or $result.manifest_sha256 -ne $pin){throw 'Owner construction evidence mismatch.'}
foreach($name in @('http_listener_started','challenge_issued','passkey_used','guardian_exchange_called','reset_authorized','execution_available','trial_started')){if($result.$name -isnot [bool] -or $result.$name -ne $false){throw 'Construction scope mismatch.'}}
foreach($log in @('owner-stdout.txt','owner-stderr.txt')){if((Get-Item -LiteralPath (Join-Path $ownerDirectory $log)).Length -ne 0){throw 'Nonempty construction diagnostics.'}}
if((Get-FileHash -LiteralPath $layout.journal_path).Hash.ToLowerInvariant() -ne $journalHash -or (Get-LocalUser AgenticGuardian).Enabled -or (Get-LocalUser AgenticPaperRuntime).Enabled){throw 'State changed or account enabled.'}
$null=& (Join-Path $PSScriptRoot 'audit_webull_guardian_release.ps1') -ExpectedManifestSha256 $pin
$links=[ordered]@{}
foreach($path in @($PSCommandPath,$configurationPath,$signedPath,$bootstrap,$layoutReceipt[0],$resultPath,$layout.journal_path,(Join-Path $PSScriptRoot 'webull_standard_owner_process.ps1'))){$links[$path]=(Get-FileHash -LiteralPath $path).Hash.ToLowerInvariant()}
$wrapper=Join-Path $root "Receipts\pinned-owner-app-wrapper-$id.json"
$value=[ordered]@{schema_version='pinned-owner-app-wrapper-v1';fixture_id=$id;manifest_sha256=$pin;configuration_path=$configurationPath;result_path=$resultPath;journal_bytes_unchanged=$true;retained_hash_links=$links;guardian_disabled=$true;runtime_disabled=$true;synthetic_context_only=$true;http_listener_started=$false;challenge_issued=$false;guardian_started=$false;passkey_used=$false;reset_authorized=$false;execution_available=$false;trial_started=$false}
$stream=[IO.File]::Open($wrapper,[IO.FileMode]::CreateNew,[IO.FileAccess]::Write)
try{$bytes=[Text.Encoding]::UTF8.GetBytes(($value | ConvertTo-Json -Depth 8));$stream.Write($bytes,0,$bytes.Length);$stream.Flush($true)}finally{$stream.Dispose()}
Write-Output "Pinned owner app construction passed under the actual standard-owner token. Accounts remain disabled. Evidence: $wrapper"
Write-Output 'No HTTP listener, challenge, passkey, guardian host, reset or broker used; real app/transport and passkey lifecycle remain unqualified.'
