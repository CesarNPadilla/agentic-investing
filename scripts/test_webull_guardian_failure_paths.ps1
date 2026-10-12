# Owner-run protected-interpreter failure checks under actual guardian token. No service or real state.
[CmdletBinding()]
param()
$ErrorActionPreference='Stop'
$pin='2cb10942c251ffec2976168ff56661181845dd2e72d0ef724a4efe32210cbad6'
$owner=[Security.Principal.WindowsIdentity]::GetCurrent()
if(-not [Environment]::Is64BitProcess -or -not ([Security.Principal.WindowsPrincipal]::new($owner)).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)){throw 'Elevated 64-bit owner PowerShell required.'}
$guardian=Get-LocalUser AgenticGuardian
if($guardian.Enabled -or (Get-LocalUser AgenticPaperRuntime).Enabled -or $guardian.SID -eq $owner.User){throw 'Distinct disabled identities required.'}
$audit=& (Join-Path $PSScriptRoot 'audit_webull_guardian_release.ps1') -ExpectedManifestSha256 $pin | ConvertFrom-Json
$root='C:\ProgramData\AgenticInvestingGuardian'
$codeAcl=Get-Acl -LiteralPath (Join-Path $root 'Code')
if(-not $codeAcl.AreAccessRulesProtected -or $codeAcl.GetOwner([Security.Principal.SecurityIdentifier]).Value -ne 'S-1-5-32-544'){throw 'Protected fixture code directory required.'}
$driver=Join-Path $PSScriptRoot 'check_webull_guardian_failure_paths.py'
$extractChildSource=@'
import ast, base64, sys
with open(sys.argv[1], encoding='utf-8-sig') as stream:
    tree = ast.parse(stream.read())
values = [node.value for node in tree.body if isinstance(node, ast.Assign)
          and len(node.targets) == 1 and isinstance(node.targets[0], ast.Name)
          and node.targets[0].id == 'CHILD']
if len(values) != 1 or not isinstance(values[0], ast.Constant) or not isinstance(values[0].value, str):
    raise ValueError('Exactly one literal CHILD source required')
print(base64.b64encode(values[0].value.encode('utf-8')).decode('ascii'))
'@
# Parse the literal without importing or executing the driver. Base64 preserves its bytes.
$encodedChild=@(& (Join-Path $audit.installed_directory 'python.exe') -I -B -c $extractChildSource $driver)
if($LASTEXITCODE -ne 0 -or $encodedChild.Count -ne 1 -or $encodedChild[0] -cnotmatch '^[A-Za-z0-9+/]+={0,2}$'){throw 'Literal failure-path source extraction failed.'}
$childBytes=[Convert]::FromBase64String($encodedChild[0])
$id=[guid]::NewGuid().ToString('N')
$childPath=Join-Path $root "Code\guardian-failure-paths-$id.py"
$stream=[IO.File]::Open($childPath,[IO.FileMode]::CreateNew,[IO.FileAccess]::Write)
try{$stream.Write($childBytes,0,$childBytes.Length);$stream.Flush($true)}finally{$stream.Dispose()}
$adminSid=[Security.Principal.SecurityIdentifier]::new('S-1-5-32-544');$systemSid=[Security.Principal.SecurityIdentifier]::new('S-1-5-18')
$childAcl=[Security.AccessControl.FileSecurity]::new();$childAcl.SetOwner($adminSid);$childAcl.SetAccessRuleProtection($true,$false)
foreach($sid in @($owner.User,$guardian.SID,$adminSid,$systemSid)){
 $rights=if($sid -eq $owner.User -or $sid -eq $guardian.SID){'ReadAndExecute'}else{'FullControl'}
 $childAcl.AddAccessRule([Security.AccessControl.FileSystemAccessRule]::new($sid,$rights,'Allow'))
}
Set-Acl -LiteralPath $childPath -AclObject $childAcl
$sections=[Security.AccessControl.AccessControlSections]::Owner -bor [Security.AccessControl.AccessControlSections]::Access
$protectedChild=Get-Acl -LiteralPath $childPath
function Child-Rules($Acl){@($Acl.GetAccessRules($true,$true,[Security.Principal.SecurityIdentifier]) | ForEach-Object {'{0}|{1}|{2}|{3}|{4}|{5}' -f $_.IdentityReference.Value,[int]$_.FileSystemRights,[int]$_.InheritanceFlags,[int]$_.PropagationFlags,[int]$_.AccessControlType,$_.IsInherited} | Sort-Object)}
if(-not $protectedChild.AreAccessRulesProtected -or $protectedChild.GetOwner([Security.Principal.SecurityIdentifier]) -ne $adminSid -or (Compare-Object (Child-Rules $protectedChild) (Child-Rules $childAcl))){throw 'Fixture child protection mismatch.'}
$childDescriptor=$protectedChild.GetSecurityDescriptorSddlForm($sections)
$childHash=(Get-FileHash $childPath -Algorithm SHA256).Hash.ToLowerInvariant()
$password=$null;$process=$null;$results=@()
try{
 $password=Read-Host 'Enter AgenticGuardian password locally (do not share it)' -AsSecureString
 Enable-LocalUser AgenticGuardian
 foreach($mode in @('missing_client','partial_frame','oversized_frame','wrong_owner_identity')){
  $start=[Diagnostics.ProcessStartInfo]::new()
  $start.FileName=Join-Path $audit.installed_directory 'python.exe'
  $start.Arguments='-I -B "'+$childPath+'" '+$mode+' '+$owner.User.Value+' '+$guardian.SID.Value
  $start.WorkingDirectory=$audit.installed_directory;$start.UserName='AgenticGuardian';$start.Domain=$env:COMPUTERNAME;$start.Password=$password
  $start.UseShellExecute=$false;$start.CreateNoWindow=$true;$start.LoadUserProfile=$false;$start.RedirectStandardError=$true;$start.RedirectStandardOutput=$true
  $start.EnvironmentVariables.Clear();foreach($name in @('SystemRoot','WINDIR')){$start.EnvironmentVariables[$name]=$env:WINDIR};$start.EnvironmentVariables['PATH']=Join-Path $env:WINDIR 'System32';foreach($name in @('TEMP','TMP')){$start.EnvironmentVariables[$name]=Join-Path $root 'Logs'}
  $process=[Diagnostics.Process]::Start($start);$handle=$process.Handle
  if($handle -eq [IntPtr]::Zero -or -not $process.WaitForExit(8000)){throw 'Guardian failure-path process unavailable or timed out.'}
  $process.WaitForExit()
  $stdout=$process.StandardOutput.ReadToEnd();$stderr=$process.StandardError.ReadToEnd()
  [IO.File]::WriteAllText((Join-Path $root "Logs\guardian-failure-$id-$mode-stdout.json"),$stdout)
  [IO.File]::WriteAllText((Join-Path $root "Logs\guardian-failure-$id-$mode-stderr.txt"),$stderr)
  if($null -eq $process.ExitCode -or $process.ExitCode -ne 0 -or $stderr.Trim()){throw "Guardian failure-path check failed: $mode; diagnostics retained."}
  $result=$stdout | ConvertFrom-Json
  if($result.scenario -ne $mode -or $result.passed -ne $true -or $result.reference_handler_calls -ne 0 -or $result.pipe_closed -ne $true -or $result.no_thread_impersonation_token -ne $true -or $result.elapsed_seconds -gt 3){throw 'Guardian failure-path scope mismatch.'}
  foreach($flag in @('execution_available','reset_performed','trial_started')){if($result.$flag -ne $false){throw 'Unexpected fixture authority.'}}
  $results+=$result;$process.Dispose();$process=$null
 }
}finally{
 try{if($process -and -not $process.HasExited){$process.Kill();$process.WaitForExit(5000)|Out-Null}}
 finally{Disable-LocalUser AgenticGuardian -ErrorAction Stop;if($password){$password.Dispose()}}
}
if((Get-LocalUser AgenticGuardian).Enabled -or (Get-LocalUser AgenticPaperRuntime).Enabled){throw 'Disabled-account verification failed.'}
if((Get-FileHash $childPath -Algorithm SHA256).Hash.ToLowerInvariant() -cne $childHash){throw 'Fixture source changed.'}
if((Get-Acl -LiteralPath $childPath).GetSecurityDescriptorSddlForm($sections) -cne $childDescriptor){throw 'Fixture child protection changed.'}
& (Join-Path $PSScriptRoot 'audit_webull_guardian_release.ps1') -ExpectedManifestSha256 $pin | Out-Null
$report=Join-Path $root "Receipts\guardian-failure-paths-result-$id.json"
$result=[ordered]@{schema_version='guardian-actual-token-failure-paths-v1';observed_at_utc=[DateTime]::UtcNow.ToString('o');probe_id=$id;scenarios=$results;actual_guardian_process_identity_verified=$true;configured_owner_from_local_owner_identity=$true;rejected_caller_scope='GUARDIAN_SELF_CALLER_NOT_CONFIGURED_OWNER';child_administrator_owned_protected_acl_verified=$true;child_source_sha256=$childHash;driver_source_sha256=(Get-FileHash $driver -Algorithm SHA256).Hash.ToLowerInvariant();wrapper_source_sha256=(Get-FileHash $PSCommandPath -Algorithm SHA256).Hash.ToLowerInvariant();installed_manifest_sha256=$pin;guardian_disabled=$true;runtime_disabled=$true;service_deployed=$false;execution_available=$false;reset_performed=$false;trial_started=$false}
$stream=[IO.File]::Open($report,[IO.FileMode]::CreateNew,[IO.FileAccess]::Write)
try{$bytes=[Text.Encoding]::UTF8.GetBytes(($result | ConvertTo-Json -Depth 5));$stream.Write($bytes,0,$bytes.Length);$stream.Flush($true)}finally{$stream.Dispose()}
Write-Output "Guardian native failure-path fixture passed (4 checks). Both accounts disabled. Evidence: $report"
Write-Output 'Guardian self-caller rejection and bounded transport failures only; unrelated identities, remote hosts, deployed owner app/service lifecycle, real signature/reference and reset remain unqualified.'
# Retain fixtures; forced wrapper termination or host crash may interrupt disabling. Inspect account state then.
