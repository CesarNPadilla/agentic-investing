# Owner-run synthetic protected guardian-server/owner-client fixture. No real review state.
[CmdletBinding()]
param([switch]$StandardOwnerClient)
$ErrorActionPreference='Stop'
$pin='2cb10942c251ffec2976168ff56661181845dd2e72d0ef724a4efe32210cbad6'
$owner=[Security.Principal.WindowsIdentity]::GetCurrent()
if(-not [Environment]::Is64BitProcess -or -not ([Security.Principal.WindowsPrincipal]::new($owner)).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)){throw 'Elevated 64-bit owner PowerShell required.'}
$guardian=Get-LocalUser AgenticGuardian
if($guardian.Enabled -or (Get-LocalUser AgenticPaperRuntime).Enabled){throw 'Both accounts must start disabled.'}
$audit=& (Join-Path $PSScriptRoot 'audit_webull_guardian_release.ps1') -ExpectedManifestSha256 $pin | ConvertFrom-Json
$release=$audit.installed_directory
$root='C:\ProgramData\AgenticInvestingGuardian'
$id=[guid]::NewGuid().ToString()
$ready=Join-Path $root "Logs\guardian-pipe-ready-$id.json"
$receipt=Join-Path $root "Receipts\guardian-pipe-result-$id.json"
$clientSource=@'
using System;
using System.Runtime.InteropServices;
using System.Security.Principal;
public static class AgenticGuardianDummyPipeClient {
 [DllImport("kernel32.dll",SetLastError=true)] static extern IntPtr OpenProcess(uint access,bool inherit,int pid);
 [DllImport("advapi32.dll",SetLastError=true)] static extern bool OpenProcessToken(IntPtr p,uint access,out IntPtr token);
 [DllImport("advapi32.dll",SetLastError=true)] static extern bool GetTokenInformation(IntPtr token,int kind,IntPtr data,uint length,out uint used);
 [DllImport("advapi32.dll",SetLastError=true)] static extern bool DuplicateTokenEx(IntPtr token,uint access,IntPtr attributes,int level,int type,out IntPtr duplicate);
 [DllImport("kernel32.dll",CharSet=CharSet.Unicode,SetLastError=true)] static extern IntPtr CreateFileW(string path,uint access,uint share,IntPtr security,uint creation,uint flags,IntPtr template);
 [DllImport("kernel32.dll",SetLastError=true)] static extern bool WriteFile(IntPtr h,byte[] b,uint size,out uint written,IntPtr overlapped);
 [DllImport("kernel32.dll",SetLastError=true)] static extern bool CloseHandle(IntPtr h);
 static int TokenInt(IntPtr token,int kind) {
  IntPtr data=Marshal.AllocHGlobal(4);uint used;
  try {if(!GetTokenInformation(token,kind,data,4,out used))throw new InvalidOperationException("Token property unavailable");return Marshal.ReadInt32(data);}
  finally {Marshal.FreeHGlobal(data);}
 }
 public static void SendStandard(string name,byte[] body) {
  string owner=WindowsIdentity.GetCurrent().User.Value;
  IntPtr standard=IntPtr.Zero,duplicate=IntPtr.Zero;
  WindowsImpersonationContext context=null;
  try {
   foreach(var process in System.Diagnostics.Process.GetProcessesByName("explorer")) {
    using(process) {
     IntPtr h=OpenProcess(0x1000,false,process.Id),candidate=IntPtr.Zero;
     if(h==IntPtr.Zero)continue;
     try {
      if(!OpenProcessToken(h,10,out candidate))continue;
      using(var identity=new WindowsIdentity(candidate)) {
       if(identity.User.Value==owner && TokenInt(candidate,18)==3 && TokenInt(candidate,20)==0) {standard=candidate;candidate=IntPtr.Zero;break;}
      }
     }finally {if(candidate!=IntPtr.Zero)CloseHandle(candidate);CloseHandle(h);}
    }
   }
   if(standard==IntPtr.Zero || !DuplicateTokenEx(standard,0xE,IntPtr.Zero,2,2,out duplicate) || TokenInt(duplicate,9)!=2)throw new InvalidOperationException("Same-owner standard impersonation token required");
   context=WindowsIdentity.Impersonate(duplicate);
   using(var identity=WindowsIdentity.GetCurrent()) {
    if(identity.User.Value!=owner || new WindowsPrincipal(identity).IsInRole(WindowsBuiltInRole.Administrator) || TokenInt(identity.Token,20)!=0)throw new InvalidOperationException("Effective standard-owner identity failed");
   }
   Send(name,body);
  }finally {
   if(context!=null) {
    try {context.Undo();context.Dispose();}catch {Environment.FailFast("Owner token restoration failed");}
    using(var identity=WindowsIdentity.GetCurrent()) {
     if(identity.User.Value!=owner || !new WindowsPrincipal(identity).IsInRole(WindowsBuiltInRole.Administrator))Environment.FailFast("Elevated owner identity restoration failed");
    }
   }
   if(duplicate!=IntPtr.Zero)CloseHandle(duplicate);
   if(standard!=IntPtr.Zero)CloseHandle(standard);
  }
 }
 public static void Send(string name,byte[] body) {
  IntPtr h=CreateFileW(@"\\.\pipe\"+name,0x100083,0,IntPtr.Zero,3,0x120000,IntPtr.Zero);
  if(h==new IntPtr(-1))throw new InvalidOperationException("Owner dummy pipe connection failed");
  try {
   byte[] frame=new byte[4+body.Length];
   frame[0]=(byte)(body.Length>>24);frame[1]=(byte)(body.Length>>16);frame[2]=(byte)(body.Length>>8);frame[3]=(byte)body.Length;
   Array.Copy(body,0,frame,4,body.Length);uint written;
   if(!WriteFile(h,frame,(uint)frame.Length,out written,IntPtr.Zero) || written!=frame.Length)throw new InvalidOperationException("Owner dummy frame write failed");
  } finally {if(!CloseHandle(h))throw new InvalidOperationException("Owner dummy handle close failed");}
 }
}
'@
# A prior fixture may have loaded an older helper in this PowerShell process.
# Compile this invocation's exact source under a fresh name; never reuse that type.
$clientTypeName='AgenticGuardianDummyPipeClient_'+[guid]::NewGuid().ToString('N')
$pipeClientType=Add-Type -TypeDefinition ($clientSource.Replace('public static class AgenticGuardianDummyPipeClient {',('public static class '+$clientTypeName+' {'))) -PassThru
$password=Read-Host 'Enter the locally held AgenticGuardian password (do not share it)' -AsSecureString
$start=[Diagnostics.ProcessStartInfo]::new()
$start.FileName=Join-Path $release 'python.exe'
$start.Arguments='-I -B "'+(Join-Path $release 'app\scripts\probe_webull_guardian_pipe.py')+'" --guardian-sid '+$guardian.SID.Value+' --owner-sid '+$owner.User.Value+' --probe-id '+$id
$start.WorkingDirectory=$release;$start.UserName='AgenticGuardian';$start.Domain=$env:COMPUTERNAME;$start.Password=$password
$start.UseShellExecute=$false;$start.CreateNoWindow=$true;$start.LoadUserProfile=$false
$start.RedirectStandardError=$true;$start.RedirectStandardOutput=$true
$start.EnvironmentVariables.Clear()
foreach($name in @('SystemRoot','WINDIR')){$start.EnvironmentVariables[$name]=$env:WINDIR}
$start.EnvironmentVariables['PATH']=Join-Path $env:WINDIR 'System32'
foreach($name in @('TEMP','TMP')){$start.EnvironmentVariables[$name]=Join-Path $root 'Logs'}
$server=$null
try{
 Enable-LocalUser AgenticGuardian
 $server=[Diagnostics.Process]::Start($start);$handle=$server.Handle
 if($handle -eq [IntPtr]::Zero){throw 'Guardian server process handle unavailable.'}
 $deadline=[DateTime]::UtcNow.AddSeconds(20)
 while(-not (Test-Path -LiteralPath $ready)){
  if($server.HasExited -or [DateTime]::UtcNow -ge $deadline){throw 'Guardian readiness failed; diagnostics will be retained.'}
  Start-Sleep -Milliseconds 50
 }
 $name=(Get-Content $ready -Raw | ConvertFrom-Json).pipe_name
 if($name -notmatch '^AgenticRequest-[0-9a-f]{32}$'){throw 'Unexpected dummy pipe handshake.'}
 $body=[Text.Encoding]::UTF8.GetBytes('{"schema_version": "guardian-pipe-dummy-v1", "id": "'+$id+'"}')
 if($StandardOwnerClient){$pipeClientType::SendStandard($name,$body)}else{$pipeClientType::Send($name,$body)}
 if(-not $server.WaitForExit(10000)){throw 'Guardian dummy pipe server timed out.'}
 $server.WaitForExit()
 if($null -eq $server.ExitCode -or $server.ExitCode -ne 0){throw 'Guardian dummy pipe server failed; diagnostics retained.'}
}finally{
 try{
  if($server){
   if(-not $server.HasExited){$server.Kill();$server.WaitForExit(5000)|Out-Null}
   if($server.HasExited){
    [IO.File]::WriteAllText((Join-Path $root "Logs\guardian-pipe-stderr-$id.txt"),$server.StandardError.ReadToEnd())
    [IO.File]::WriteAllText((Join-Path $root "Logs\guardian-pipe-stdout-$id.txt"),$server.StandardOutput.ReadToEnd())
   }
  }
 }finally{Disable-LocalUser AgenticGuardian -ErrorAction Stop;$password.Dispose()}
}
if((Get-LocalUser AgenticGuardian).Enabled -or (Get-LocalUser AgenticPaperRuntime).Enabled){throw 'Disabled-account verification failed.'}
$result=Get-Content $receipt -Raw | ConvertFrom-Json
if($result.schema_version -ne 'guardian-native-pipe-fixture-v1' -or $result.probe_id -ne $id -or $result.guardian_process_identity_verified -ne $true -or $result.owner_pipe_identity_observed -ne $true -or $result.synthetic_request_only -ne $true -or $result.execution_available -ne $false -or $result.reset_performed -ne $false -or $result.trial_started -ne $false){throw 'Guardian fixture scope failed.'}
if((Get-Item (Join-Path $root "Logs\guardian-pipe-stderr-$id.txt")).Length -ne 0){throw 'Guardian diagnostic error log is not empty.'}
# Read-only recheck: no installed source mutation is accepted.
& (Join-Path $PSScriptRoot 'audit_webull_guardian_release.ps1') -ExpectedManifestSha256 $pin | Out-Null
$summaryPath=Join-Path $root "Receipts\guardian-pipe-wrapper-result-$id.json"
$summary=[ordered]@{schema_version='guardian-pipe-wrapper-fixture-v1';probe_id=$id;observed_at_utc=[DateTime]::UtcNow.ToString('o');client_mode=$(if($StandardOwnerClient){'SAME_OWNER_STANDARD_DESKTOP_TOKEN'}else{'ELEVATED_OWNER_TOKEN'});effective_standard_owner_token_verified=[bool]$StandardOwnerClient;owner_identity_restored=$true;guardian_receipt_sha256=(Get-FileHash -LiteralPath $receipt -Algorithm SHA256).Hash.ToLowerInvariant();wrapper_sha256=(Get-FileHash -LiteralPath $PSCommandPath -Algorithm SHA256).Hash.ToLowerInvariant();installed_manifest_sha256=$pin;guardian_disabled=$true;runtime_disabled=$true;execution_available=$false;reset_performed=$false;trial_started=$false}
$stream=[IO.File]::Open($summaryPath,[IO.FileMode]::CreateNew,[IO.FileAccess]::Write)
try{$bytes=[Text.Encoding]::UTF8.GetBytes(($summary | ConvertTo-Json));$stream.Write($bytes,0,$bytes.Length);$stream.Flush($true)}finally{$stream.Dispose()}
Write-Output "Protected guardian native pipe fixture passed. Account disabled again. Evidence: $receipt"
Write-Output "Client mode: $($summary.client_mode). Wrapper evidence: $summaryPath"
Write-Output 'Synthetic request only; deployed owner app, runtime rejection, service lifecycle, real signature/reference, remote-host denial and reset remain unqualified.'
# Host crash/forced wrapper termination can interrupt disabling; retain fixtures and inspect account state.
