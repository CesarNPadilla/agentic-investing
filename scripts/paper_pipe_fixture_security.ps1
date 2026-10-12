# Handle-only label adjustment for the disposable owner-run pipe fixture.
function Set-PaperFixturePipeMediumLabel {
    param([Parameter(Mandatory=$true)][System.IO.Pipes.NamedPipeServerStream]$Pipe)
    if(-not ('AgenticPipeFixtureLabel' -as [type])){
        Add-Type -TypeDefinition @'
using System;
using System.Runtime.InteropServices;
public static class AgenticPipeFixtureLabel {
 [DllImport("advapi32.dll",CharSet=CharSet.Unicode,SetLastError=true)] static extern bool ConvertStringSecurityDescriptorToSecurityDescriptor(string text,uint revision,out IntPtr descriptor,out uint size);
 [DllImport("advapi32.dll",SetLastError=true)] static extern bool GetSecurityDescriptorSacl(IntPtr descriptor,out bool present,out IntPtr acl,out bool defaulted);
 [DllImport("advapi32.dll")] static extern uint SetSecurityInfo(IntPtr handle,uint objectType,uint securityInfo,IntPtr owner,IntPtr group,IntPtr dacl,IntPtr sacl);
 [DllImport("advapi32.dll")] static extern uint GetSecurityInfo(IntPtr handle,uint objectType,uint securityInfo,out IntPtr owner,out IntPtr group,out IntPtr dacl,out IntPtr sacl,out IntPtr descriptor);
 [DllImport("advapi32.dll",CharSet=CharSet.Unicode,SetLastError=true)] static extern bool ConvertSecurityDescriptorToStringSecurityDescriptor(IntPtr descriptor,uint revision,uint info,out IntPtr text,out uint size);
 [DllImport("kernel32.dll")] static extern IntPtr LocalFree(IntPtr value);
 public static void SetMedium(IntPtr handle){
   IntPtr sd;uint size;
   if(!ConvertStringSecurityDescriptorToSecurityDescriptor("S:(ML;;NW;;;ME)",1,out sd,out size))throw new System.ComponentModel.Win32Exception();
   try{
     bool present,defaulted;IntPtr acl;
     if(!GetSecurityDescriptorSacl(sd,out present,out acl,out defaulted)||!present)throw new System.ComponentModel.Win32Exception();
     // LABEL_SECURITY_INFORMATION only: no DACL, owner or filesystem modification.
     uint error=SetSecurityInfo(handle,6,16,IntPtr.Zero,IntPtr.Zero,IntPtr.Zero,acl);
     if(error!=0)throw new System.ComponentModel.Win32Exception((int)error);
   }finally{LocalFree(sd);}
 }
 public static string ReadLabel(IntPtr handle){
   IntPtr owner,group,dacl,sacl,sd;
   uint error=GetSecurityInfo(handle,6,16,out owner,out group,out dacl,out sacl,out sd);
   if(error!=0)throw new System.ComponentModel.Win32Exception((int)error);
   try{
     IntPtr text;uint size;
     if(!ConvertSecurityDescriptorToStringSecurityDescriptor(sd,1,16,out text,out size))throw new System.ComponentModel.Win32Exception();
     try{return Marshal.PtrToStringUni(text);}finally{LocalFree(text);}
   }finally{LocalFree(sd);}
 }
}
'@
    }
    $handle=$Pipe.SafePipeHandle.DangerousGetHandle()
    $before=[AgenticPipeFixtureLabel]::ReadLabel($handle)
    [AgenticPipeFixtureLabel]::SetMedium($handle)
    $after=[AgenticPipeFixtureLabel]::ReadLabel($handle)
    if($after -notmatch '\(ML;;NW;;;ME\)'){throw 'Temporary pipe medium integrity label not verified.'}
    return [pscustomobject]@{Before=$before;After=$after;MediumLabelVerified=$true}
}
