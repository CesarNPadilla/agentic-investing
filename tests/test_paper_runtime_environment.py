import base64
import json
import os
import subprocess
import sys

import pytest

from workers.paper_runtime_environment import build_runtime_environment


def environment(**changes):
    settings = {
        "windows_root": r"C:\Windows",
        "runtime_profile": r"C:\Users\AgenticPaperRuntime",
        "runtime_temp": r"C:\Users\AgenticPaperRuntime\AppData\Local\Temp",
    }
    return build_runtime_environment(**(settings | changes))


def test_parent_secrets_and_python_overrides_are_not_copied(monkeypatch):
    for key in [
        "AIL_WEBULL_APP_SECRET",
        "APCA_API_SECRET_KEY",
        "PYTHONPATH",
        "PYTHONHOME",
        "HTTP_PROXY",
    ]:
        monkeypatch.setenv(key, "SYNTHETIC-DO-NOT-INHERIT")
    result = environment()
    assert set(result) == {
        "SystemRoot",
        "WINDIR",
        "COMSPEC",
        "PATHEXT",
        "PSMODULEPATH",
        "PATH",
        "USERPROFILE",
        "APPDATA",
        "LOCALAPPDATA",
        "TEMP",
        "TMP",
        "PYTHONNOUSERSITE",
        "PYTHONSAFEPATH",
    }
    assert "SYNTHETIC-DO-NOT-INHERIT" not in result.values()
    assert result["PATH"].split(";")[0] == r"C:\Windows\System32"


@pytest.mark.parametrize(
    "path",
    [
        r"relative\path",
        r"\\server\share",
        r"C:\Temp;C:\evil",
        r"C:\%TEMP%",
        r"C:\Temp\..\Owner",
        "C:\\Temp\nInjected",
        r"C:\Temp:stream",
    ],
)
def test_unsafe_controller_path_is_rejected(path):
    with pytest.raises(ValueError):
        environment(runtime_profile=path)


@pytest.mark.parametrize(
    "path",
    [
        r"C:\Users\Owner\Temp",
        r"C:\Users\AgenticPaperRuntimeOther\Temp",
        r"D:\Temp",
        r"C:\Users\AgenticPaperRuntime",
    ],
)
def test_temp_cannot_escape_dedicated_profile(path):
    with pytest.raises(ValueError):
        environment(runtime_temp=path)


def test_actual_isolated_child_does_not_inherit_synthetic_secret(monkeypatch, tmp_path):
    monkeypatch.setenv("AGENTIC_SYNTHETIC_PARENT_SECRET", "DUMMY-NO-SECRETS")
    result = subprocess.run(
        [
            sys.executable,
            "-I",
            "-c",
            "import json,os; print(json.dumps({'marker_absent':'AGENTIC_SYNTHETIC_PARENT_SECRET' not in os.environ,'pythonpath_absent':'PYTHONPATH' not in os.environ,'no_user_site':os.environ.get('PYTHONNOUSERSITE')=='1'}))",
        ],
        env=environment(windows_root=os.environ["SystemRoot"]),
        cwd=tmp_path,
        capture_output=True,
        text=True,
        timeout=10,
        check=True,
        close_fds=True,
        creationflags=subprocess.CREATE_NO_WINDOW,
    )
    assert json.loads(result.stdout) == {
        "marker_absent": True,
        "pythonpath_absent": True,
        "no_user_site": True,
    }


@pytest.mark.parametrize("execution_policy", [None, "Bypass"])
def test_actual_dotnet_launch_replaces_parent_environment(monkeypatch, execution_policy):
    monkeypatch.setenv("AGENTIC_SYNTHETIC_PARENT_SECRET", "DUMMY-NO-SECRETS")
    values = environment(windows_root=os.environ["SystemRoot"])
    encoded_environment = base64.b64encode(json.dumps(values).encode()).decode()
    child = (
        "$ProgressPreference='SilentlyContinue';"
        "[pscustomobject]@{MarkerAbsent=(-not [Environment]::GetEnvironmentVariables()"
        ".Contains('AGENTIC_SYNTHETIC_PARENT_SECRET'));"
        "Keys=@([Environment]::GetEnvironmentVariables().Keys);"
        "Policy=[Environment]::GetEnvironmentVariable('PSExecutionPolicyPreference')} | ConvertTo-Json"
    )
    encoded_child = base64.b64encode(child.encode("utf-16-le")).decode()
    policy_option = "-ExecutionPolicy Bypass " if execution_policy else ""
    script = (
        "$ErrorActionPreference='Stop';"
        f"$values=[Text.Encoding]::UTF8.GetString([Convert]::FromBase64String('{encoded_environment}')) | ConvertFrom-Json;"
        "$start=[Diagnostics.ProcessStartInfo]::new();"
        r"$start.FileName=Join-Path $values.SystemRoot 'System32\WindowsPowerShell\v1.0\powershell.exe';"
        "$start.UseShellExecute=$false;$start.CreateNoWindow=$true;"
        "$start.WindowStyle=[Diagnostics.ProcessWindowStyle]::Hidden;"
        "$start.RedirectStandardOutput=$true;$start.RedirectStandardError=$true;"
        "$start.RedirectStandardInput=$true;$start.EnvironmentVariables.Clear();"
        "foreach($p in $values.PSObject.Properties){$start.EnvironmentVariables[$p.Name]=[string]$p.Value};"
        f"$start.Arguments='-NoProfile -NonInteractive {policy_option}-EncodedCommand {encoded_child}';"
        "$p=[Diagnostics.Process]::Start($start);$p.StandardInput.Close();"
        "try{$out=$p.StandardOutput.ReadToEndAsync();$err=$p.StandardError.ReadToEndAsync();"
        "if(-not $p.WaitForExit(10000)){throw 'Child timeout'};$p.WaitForExit();"
        "if($p.ExitCode -ne 0 -or $err.GetAwaiter().GetResult().Length -ne 0){throw 'Child failed'};"
        "$out.GetAwaiter().GetResult()}finally{if(-not $p.HasExited){$p.Kill();$p.WaitForExit()};$p.Dispose()}"
    )
    result = subprocess.run(
        ["powershell.exe", "-NoProfile", "-NonInteractive", "-Command", script],
        capture_output=True,
        text=True,
        timeout=20,
        check=True,
        creationflags=subprocess.CREATE_NO_WINDOW,
    )
    observed = json.loads(result.stdout)
    assert observed["MarkerAbsent"] is True
    expected = {key.casefold() for key in values}
    if execution_policy:
        expected.add("psexecutionpolicypreference")
    assert {key.casefold() for key in observed["Keys"]} == expected
    assert observed["Policy"] == execution_policy
