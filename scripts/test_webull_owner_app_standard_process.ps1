# Missing-state app diagnostic using the existing same-owner standard desktop token.
[CmdletBinding()]
param()
$ErrorActionPreference='Stop'
$owner=[Security.Principal.WindowsIdentity]::GetCurrent()
if(-not ([Security.Principal.WindowsPrincipal]::new($owner)).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)){throw 'Elevated owner launcher required.'}
if((Get-LocalUser AgenticGuardian).Enabled -or (Get-LocalUser AgenticPaperRuntime).Enabled){throw 'Both accounts must remain disabled.'}
. (Join-Path $PSScriptRoot 'webull_standard_owner_process.ps1')
$launcher=New-StandardOwnerLauncher
$id=[guid]::NewGuid().ToString('N')
$directory=Join-Path $env:LOCALAPPDATA "AgenticInvesting\staging\owner-standard-process-$id"
New-Item -ItemType Directory -Path $directory | Out-Null
$bootstrap=Join-Path $directory 'bootstrap.py'
$driver=Join-Path $PSScriptRoot 'check_webull_owner_app_lifecycle.py'
$stdout=Join-Path $directory 'stdout.txt';$stderr=Join-Path $directory 'stderr.txt'
$config=@{driver=$driver;stdout=$stdout;stderr=$stderr;owner=$owner.User.Value} | ConvertTo-Json -Compress
# JSON is data encoded inside a Python string, never shell code.
$literal=ConvertTo-Json -InputObject $config -Compress
$pythonSource="import json,runpy,sys`nc=json.loads($literal)`nsys.stdout=open(c['stdout'],'x',encoding='utf-8')`nsys.stderr=open(c['stderr'],'x',encoding='utf-8')`nsys.argv=[c['driver'],'--standard-owner-sid',c['owner']]`nrunpy.run_path(c['driver'],run_name='__main__')`n"
[IO.File]::WriteAllText($bootstrap,$pythonSource,[Text.UTF8Encoding]::new($false))
$python='C:\ProgramData\AgenticInvestingPaper\OwnerControl\WebullReviewEnvironment-f2eb1b3b90ce7a79\python.exe'
$variables=@{SystemRoot=$env:WINDIR;WINDIR=$env:WINDIR;PATH=(Join-Path $env:WINDIR 'System32');LOCALAPPDATA=$env:LOCALAPPDATA;TEMP=$directory;TMP=$directory}
$environment=(@($variables.Keys | Sort-Object | ForEach-Object {$_+'='+$variables[$_]}) -join [char]0)+[char]0+[char]0
$exit=$launcher::Run($python,('"'+$python+'" -I -B "'+$bootstrap+'"'),$environment,$directory)
if($exit -ne 0){throw "Standard owner diagnostic failed (exit $exit). Retained diagnostic log: $stderr"}
$receipt=(Get-Content -LiteralPath $stdout -Raw).Trim()
$result=Get-Content -LiteralPath $receipt -Raw | ConvertFrom-Json
if($result.standard_owner_token_qualified -ne $true -or $result.scope -cne 'INSTALLED_OWNER_APP_STANDARD_OWNER_TOKEN_MISSING_STATE_FORCED_PROCESS_SHUTDOWN' -or $result.listener_closed -ne $true -or $result.private_state_created -ne $false -or @($result.checks).Count -ne 10){throw 'Standard process diagnostic scope failed.'}
if((Get-LocalUser AgenticGuardian).Enabled -or (Get-LocalUser AgenticPaperRuntime).Enabled){throw 'Disabled accounts changed.'}
$record=[ordered]@{schema_version='owner-standard-app-process-wrapper-v1';receipt_path=$receipt;receipt_sha256=(Get-FileHash -LiteralPath $receipt -Algorithm SHA256).Hash.ToLowerInvariant();launcher_sha256=(Get-FileHash -LiteralPath $PSCommandPath -Algorithm SHA256).Hash.ToLowerInvariant();driver_sha256=(Get-FileHash -LiteralPath $driver -Algorithm SHA256).Hash.ToLowerInvariant();bootstrap_sha256=(Get-FileHash -LiteralPath $bootstrap -Algorithm SHA256).Hash.ToLowerInvariant();standard_owner_process_verified=$true;guardian_disabled=$true;runtime_disabled=$true;execution_available=$false;reset_authorized=$false;trial_started=$false}
$recordPath=Join-Path $directory 'wrapper-result.json'
[IO.File]::WriteAllText($recordPath,($record | ConvertTo-Json),[Text.UTF8Encoding]::new($false))
Write-Output "Standard-owner missing-state app process verified. Evidence: $recordPath"
