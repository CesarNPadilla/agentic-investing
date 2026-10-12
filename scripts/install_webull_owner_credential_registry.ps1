# Immutable binding record only; no current-key selector, review, service or activation.
[CmdletBinding()]
param(
 [Parameter(Mandatory=$true)][string]$CandidatePath,
 [Parameter(Mandatory=$true)][ValidatePattern('^[0-9a-f]{64}$')][string]$ExpectedCandidateSha256
)
$ErrorActionPreference='Stop'
$owner=[Security.Principal.WindowsIdentity]::GetCurrent()
if(-not [Environment]::Is64BitProcess -or -not ([Security.Principal.WindowsPrincipal]::new($owner)).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)){throw 'Elevated 64-bit owner required.'}
$guardian=Get-LocalUser AgenticGuardian
if($guardian.Enabled -or (Get-LocalUser AgenticPaperRuntime).Enabled){throw 'Both accounts must remain disabled.'}
$repo=Split-Path $PSScriptRoot -Parent
$python=Join-Path $repo '.venv\Scripts\python.exe'
$candidate=Get-Item -LiteralPath $CandidatePath -Force
if($candidate.PSIsContainer -or $candidate.Length -gt 32768 -or ($candidate.Attributes -band [IO.FileAttributes]::ReparsePoint)){throw 'Bounded ordinary candidate required.'}
$target='C:\ProgramData\AgenticInvestingGuardian\Code\AcceptedOwnerCredential-'+$ExpectedCandidateSha256+'.json'
if(Test-Path -LiteralPath $target){throw 'Immutable destination already exists; audit it, do not overwrite.'}
$code=@'
import hashlib,sys
from pathlib import Path
from security.webull_owner_credential_registry import parse_registry
p,pin,owner,guardian=sys.argv[1:5]
raw=Path(p).read_bytes()
parse_registry(raw,expected_sha256=pin,credential_sha256='fc0761142d56f020eac42868d377fb12849458e90a6db5c23edc9bc6ca58e22b',owner_sid=owner,guardian_sid=guardian)
'@
$encoded=[Convert]::ToBase64String([Text.Encoding]::UTF8.GetBytes($code))
Push-Location $repo
try{& $python -B -c "import base64;exec(base64.b64decode('$encoded'))" $CandidatePath $ExpectedCandidateSha256 $owner.User.Value $guardian.SID.Value
 if($LASTEXITCODE -ne 0){throw 'Independent binding signature/material verification failed.'}
}finally{Pop-Location}
$bytes=[IO.File]::ReadAllBytes($CandidatePath)
$sha=[Security.Cryptography.SHA256]::Create()
try{$digest=([BitConverter]::ToString($sha.ComputeHash($bytes))).Replace('-','').ToLowerInvariant()}finally{$sha.Dispose()}
if($digest -cne $ExpectedCandidateSha256){throw 'Candidate changed after verification.'}
$admin=[Security.Principal.SecurityIdentifier]::new('S-1-5-32-544')
$system=[Security.Principal.SecurityIdentifier]::new('S-1-5-18')
$acl=[Security.AccessControl.FileSecurity]::new();$acl.SetOwner($admin);$acl.SetAccessRuleProtection($true,$false)
foreach($sid in @($admin,$system,$owner.User,$guardian.SID)){
 $rights=if($sid -eq $admin -or $sid -eq $system){'FullControl'}else{'ReadAndExecute'}
 $acl.AddAccessRule([Security.AccessControl.FileSystemAccessRule]::new($sid,$rights,'Allow'))
}
$stream=[IO.File]::Open($target,[IO.FileMode]::CreateNew,[IO.FileAccess]::Write)
try{$stream.Write($bytes,0,$bytes.Length);$stream.Flush($true)}finally{$stream.Dispose()}
Set-Acl -LiteralPath $target -AclObject $acl
function Rules($value){@($value.GetAccessRules($true,$true,[Security.Principal.SecurityIdentifier]) | ForEach-Object {'{0}|{1}|{2}|{3}|{4}|{5}' -f $_.IdentityReference.Value,[int]$_.FileSystemRights,[int]$_.InheritanceFlags,[int]$_.PropagationFlags,[int]$_.AccessControlType,$_.IsInherited} | Sort-Object)}
$actual=Get-Acl -LiteralPath $target
if(-not $actual.AreAccessRulesProtected -or $actual.GetOwner([Security.Principal.SecurityIdentifier]) -ne $admin -or (Compare-Object (Rules $acl) (Rules $actual)) -or (Get-FileHash -LiteralPath $target).Hash.ToLowerInvariant() -cne $ExpectedCandidateSha256){throw 'Installed registry audit failed; retain partial record.'}
Write-Output "Immutable owner credential binding record installed: $target"
Write-Output 'No active key selector or app/service integration installed; accounts remain disabled. No review, reset or trading approved.'
