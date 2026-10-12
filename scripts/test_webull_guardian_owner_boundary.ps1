# Handle-only standard-owner desktop token check. No accounts enabled or permissions changed.
[CmdletBinding()]
param()
$ErrorActionPreference='Stop'
$principal=[Security.Principal.WindowsPrincipal]::new([Security.Principal.WindowsIdentity]::GetCurrent())
if(-not [Environment]::Is64BitProcess -or -not $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)){throw 'Elevated 64-bit owner PowerShell required.'}
if((Get-LocalUser AgenticGuardian).Enabled -or (Get-LocalUser AgenticPaperRuntime).Enabled){throw 'Both accounts must be disabled.'}
$root='C:\ProgramData\AgenticInvestingGuardian'
$sections=[Security.AccessControl.AccessControlSections]::Access -bor [Security.AccessControl.AccessControlSections]::Owner
$paths=@($root,(Join-Path $root 'Code'),(Join-Path $root 'Config'),(Join-Path $root 'References'),(Join-Path $root 'Receipts'),(Join-Path $root 'Logs'))
$before=@{}
foreach($path in $paths){
 $item=Get-Item -LiteralPath $path -Force
 if(-not $item.PSIsContainer -or ($item.Attributes -band [IO.FileAttributes]::ReparsePoint)){throw 'Non-reparse guardian layout required.'}
 $acl=Get-Acl -LiteralPath $path
 if(-not $acl.AreAccessRulesProtected -or $acl.GetOwner([Security.Principal.SecurityIdentifier]).Value -ne 'S-1-5-32-544'){throw 'Protected administrator-owned layout required.'}
 $before[$path]=$acl.GetSecurityDescriptorSddlForm($sections)
}
Add-Type -TypeDefinition @'
using System;
using System.Collections.Generic;
using System.Runtime.InteropServices;
using System.Security.Principal;
public static class AgenticGuardianOwnerBoundary {
 [DllImport("kernel32.dll")] static extern IntPtr GetCurrentProcess();
 [DllImport("kernel32.dll", SetLastError=true)] static extern IntPtr OpenProcess(uint access,bool inherit,int pid);
 [DllImport("kernel32.dll", SetLastError=true)] static extern bool CloseHandle(IntPtr h);
 [DllImport("advapi32.dll", SetLastError=true)] static extern bool OpenProcessToken(IntPtr p,uint a,out IntPtr h);
 [DllImport("advapi32.dll", SetLastError=true)] static extern bool GetTokenInformation(IntPtr h,int c,IntPtr b,uint n,out uint used);
 [DllImport("advapi32.dll", SetLastError=true)] static extern bool DuplicateTokenEx(IntPtr h,uint access,IntPtr attributes,int level,int type,out IntPtr duplicate);
 [DllImport("kernel32.dll",CharSet=CharSet.Unicode,SetLastError=true)] static extern IntPtr CreateFileW(string p,uint a,uint share,IntPtr s,uint creation,uint flags,IntPtr template);
 public class Check { public string Area; public string Right; public int Win32Error; public bool ExpectedDenied; public bool Passed; }
 static int TokenInt(IntPtr token,int kind) {
  IntPtr data=Marshal.AllocHGlobal(4); uint used;
  try { if(!GetTokenInformation(token,kind,data,4,out used))throw new InvalidOperationException("Token property unavailable");return Marshal.ReadInt32(data); }
  finally { Marshal.FreeHGlobal(data); }
 }
 static int Open(string path,uint access) {
  IntPtr h=CreateFileW(path,access,7,IntPtr.Zero,3,0x02000000,IntPtr.Zero);
  if(h==new IntPtr(-1))return Marshal.GetLastWin32Error();
  if(!CloseHandle(h))throw new InvalidOperationException("Probe handle close failed");return 0;
 }
 public static Check[] Run(string root) {
  string owner=WindowsIdentity.GetCurrent().User.Value;
  IntPtr current=IntPtr.Zero,standard=IntPtr.Zero,duplicate=IntPtr.Zero;
  var checks=new List<Check>(); WindowsImpersonationContext context=null;
  try {
   if(!OpenProcessToken(GetCurrentProcess(),8,out current) || TokenInt(current,18)!=2)throw new InvalidOperationException("UAC elevated owner token required");
   foreach(var process in System.Diagnostics.Process.GetProcessesByName("explorer")) {
    using(process) {
     IntPtr handle=OpenProcess(0x1000,false,process.Id),candidate=IntPtr.Zero;
     if(handle==IntPtr.Zero)continue;
     try {
      if(!OpenProcessToken(handle,10,out candidate))continue;
      using(var identity=new WindowsIdentity(candidate)) {
       if(identity.User.Value==owner && TokenInt(candidate,18)==3 && TokenInt(candidate,20)==0) {standard=candidate;candidate=IntPtr.Zero;break;}
      }
     } finally {if(candidate!=IntPtr.Zero)CloseHandle(candidate);CloseHandle(handle);}
    }
   }
   if(standard==IntPtr.Zero)throw new InvalidOperationException("Existing same-owner non-elevated Explorer token required");
   if(!DuplicateTokenEx(standard,0xE,IntPtr.Zero,2,2,out duplicate))throw new InvalidOperationException("Standard-owner impersonation token unavailable");
   if(TokenInt(duplicate,9)!=2)throw new InvalidOperationException("SecurityImpersonation level required");
   context=WindowsIdentity.Impersonate(duplicate);
   using(var actual=WindowsIdentity.GetCurrent()) {
    if(actual.User.Value!=owner || new WindowsPrincipal(actual).IsInRole(WindowsBuiltInRole.Administrator) || TokenInt(actual.Token,20)!=0)throw new InvalidOperationException("Effective standard-owner token failed");
   }
   string[] areas={"Root","Code","Config","References","Receipts","Logs"};
   string[] rights={"DELETE","DELETE_CHILD","ADD_FILE","ADD_SUBDIRECTORY","WRITE_DAC","WRITE_OWNER"};
   uint[] masks={0x10000,0x40,2,4,0x40000,0x80000};
   foreach(string area in areas) {
    string path=area=="Root"?root:System.IO.Path.Combine(root,area);
    int read=Open(path,0x20000);
    checks.Add(new Check{Area=area,Right="READ_CONTROL",Win32Error=read,ExpectedDenied=false,Passed=read==0});
    for(int i=0;i<rights.Length;i++) {
     int error=Open(path,masks[i]);checks.Add(new Check{Area=area,Right=rights[i],Win32Error=error,ExpectedDenied=true,Passed=error==5});
    }
   }
   int parent=Open(System.IO.Directory.GetParent(root).FullName,0x40);
   checks.Add(new Check{Area="ProgramDataParent",Right="DELETE_CHILD",Win32Error=parent,ExpectedDenied=true,Passed=parent==5});
  } finally {
   if(context!=null) {
    try {context.Undo();context.Dispose();}
    catch {Environment.FailFast("Cannot restore owner identity after handle probe");}
    using(var restored=WindowsIdentity.GetCurrent()) {
     if(restored.User.Value!=owner || !new WindowsPrincipal(restored).IsInRole(WindowsBuiltInRole.Administrator))Environment.FailFast("Owner identity restoration failed");
    }
   }
   if(standard!=IntPtr.Zero)CloseHandle(standard);
   if(duplicate!=IntPtr.Zero)CloseHandle(duplicate);
   if(current!=IntPtr.Zero)CloseHandle(current);
  }
  return checks.ToArray();
 }
}
'@
$checks=@([AgenticGuardianOwnerBoundary]::Run($root))
if($checks.Count -ne 43 -or @($checks | Where-Object {-not $_.Passed}).Count){throw 'Standard-owner boundary check failed; no permissions were changed.'}
foreach($path in $paths){if((Get-Acl -LiteralPath $path).GetSecurityDescriptorSddlForm($sections) -ne $before[$path]){throw 'Guardian directory descriptor changed.'}}
if((Get-LocalUser AgenticGuardian).Enabled -or (Get-LocalUser AgenticPaperRuntime).Enabled){throw 'Disabled-account verification failed.'}
$result=[ordered]@{schema_version='guardian-owner-desktop-token-boundary-v1';observed_at_utc=[DateTime]::UtcNow.ToString('o');token_source='EXISTING_SAME_OWNER_NON_ELEVATED_EXPLORER';same_owner_limited_token_verified=$true;effective_non_admin_verified=$true;owner_identity_restored=$true;checks=$checks;directory_descriptors_unchanged=$true;guardian_disabled=$true;runtime_disabled=$true;execution_available=$false;reset_performed=$false;trial_started=$false}
$resultPath=Join-Path $root ('Receipts\owner-boundary-result-'+[guid]::NewGuid().ToString('N')+'.json')
$stream=[IO.File]::Open($resultPath,[IO.FileMode]::CreateNew,[IO.FileAccess]::Write)
try{$bytes=[Text.Encoding]::UTF8.GetBytes(($result | ConvertTo-Json -Depth 5));$stream.Write($bytes,0,$bytes.Length);$stream.Flush($true)}finally{$stream.Dispose()}
Write-Output "Standard-owner desktop-token boundary passed (37 denied, 6 read controls). Evidence: $resultPath"
Write-Output 'Handle opens only; no delete, permission/ownership change, account enable, process deployment, service, reset or broker call.'
