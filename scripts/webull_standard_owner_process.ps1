# Creates a fresh launcher type; never starts a process until Run is called.
function New-StandardOwnerLauncher {
$source=@'
using System;
using System.Text;
using System.Runtime.InteropServices;
using System.Security.Principal;
public static class OwnerStandardProcess {
 [StructLayout(LayoutKind.Sequential,CharSet=CharSet.Unicode)] struct Startup {
  public int cb; public string reserved,desktop,title;
  public uint x,y,xSize,ySize,xCount,yCount,fill,flags;
  public short show,reservedSize; public IntPtr reserved2,input,output,error;
 }
 [StructLayout(LayoutKind.Sequential)] struct ProcessInfo {public IntPtr process,thread;public uint pid,tid;}
 [DllImport("kernel32.dll",SetLastError=true)] static extern IntPtr OpenProcess(uint access,bool inherit,int pid);
 [DllImport("advapi32.dll",SetLastError=true)] static extern bool OpenProcessToken(IntPtr process,uint access,out IntPtr token);
 [DllImport("advapi32.dll",SetLastError=true)] static extern bool GetTokenInformation(IntPtr token,int kind,IntPtr data,uint length,out uint used);
 [DllImport("advapi32.dll",SetLastError=true)] static extern bool DuplicateTokenEx(IntPtr token,uint access,IntPtr attrs,int level,int kind,out IntPtr duplicate);
 [DllImport("advapi32.dll",CharSet=CharSet.Unicode,SetLastError=true)] static extern bool CreateProcessWithTokenW(IntPtr token,uint logon,string app,StringBuilder command,uint flags,IntPtr environment,string directory,ref Startup startup,out ProcessInfo process);
 [DllImport("kernel32.dll")] static extern uint WaitForSingleObject(IntPtr h,uint milliseconds);
 [DllImport("kernel32.dll")] static extern bool GetExitCodeProcess(IntPtr h,out uint exitCode);
 [DllImport("kernel32.dll")] static extern bool TerminateProcess(IntPtr h,uint exitCode);
 [DllImport("kernel32.dll")] static extern bool CloseHandle(IntPtr h);
 static int TokenInt(IntPtr token,int kind) {
  IntPtr data=Marshal.AllocHGlobal(4);uint used;
  try {if(!GetTokenInformation(token,kind,data,4,out used))throw new InvalidOperationException("Token property unavailable");return Marshal.ReadInt32(data);}
  finally {Marshal.FreeHGlobal(data);}
 }
 public static uint Run(string application,string command,string environment,string directory) {
  string owner=WindowsIdentity.GetCurrent().User.Value;
  IntPtr standard=IntPtr.Zero,duplicate=IntPtr.Zero,env=IntPtr.Zero;
  ProcessInfo child=new ProcessInfo();
  try {
   foreach(var process in System.Diagnostics.Process.GetProcessesByName("explorer")) {
    using(process) {
     IntPtr h=OpenProcess(0x1000,false,process.Id),candidate=IntPtr.Zero;
     if(h==IntPtr.Zero)continue;
     try {
      if(!OpenProcessToken(h,10,out candidate))continue;
      using(var identity=new WindowsIdentity(candidate)) {
       if(identity.User.Value==owner && TokenInt(candidate,18)==3 && TokenInt(candidate,20)==0){standard=candidate;candidate=IntPtr.Zero;break;}
      }
     }finally {if(candidate!=IntPtr.Zero)CloseHandle(candidate);CloseHandle(h);}
    }
   }
   if(standard==IntPtr.Zero || !DuplicateTokenEx(standard,0x2000000,IntPtr.Zero,2,1,out duplicate) || TokenInt(duplicate,8)!=1 || TokenInt(duplicate,20)!=0)throw new InvalidOperationException("Same-owner standard primary token required");
   env=Marshal.StringToHGlobalUni(environment);
   Startup startup=new Startup();startup.cb=Marshal.SizeOf(startup);
   if(!CreateProcessWithTokenW(duplicate,0,application,new StringBuilder(command),0x08000400,env,directory,ref startup,out child))throw new InvalidOperationException("Standard process launch failed: "+Marshal.GetLastWin32Error());
   if(WaitForSingleObject(child.process,50000)!=0){TerminateProcess(child.process,72);WaitForSingleObject(child.process,5000);throw new TimeoutException("Standard app diagnostic exceeded bounded wait");}
   uint exitCode;if(!GetExitCodeProcess(child.process,out exitCode))throw new InvalidOperationException("Standard process result unavailable");
   return exitCode;
  }finally {
   if(child.thread!=IntPtr.Zero)CloseHandle(child.thread);
   if(child.process!=IntPtr.Zero)CloseHandle(child.process);
   if(env!=IntPtr.Zero)Marshal.FreeHGlobal(env);
   if(duplicate!=IntPtr.Zero)CloseHandle(duplicate);
   if(standard!=IntPtr.Zero)CloseHandle(standard);
  }
 }
}
'@
$typeName='OwnerStandardProcess_'+[guid]::NewGuid().ToString('N')
$launcher=Add-Type -TypeDefinition ($source.Replace('public static class OwnerStandardProcess {','public static class '+$typeName+' {')) -PassThru | Where-Object Name -CEQ $typeName
return $launcher
}
