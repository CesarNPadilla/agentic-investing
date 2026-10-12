"""Installed native failure paths under engineering identity; no account or service changes."""

import hashlib
import json
import subprocess
from datetime import UTC, datetime
from pathlib import Path

PIN = "2cb10942c251ffec2976168ff56661181845dd2e72d0ef724a4efe32210cbad6"
RELEASE = Path(r"C:\ProgramData\AgenticInvestingGuardian\Code") / ("GuardianRelease-" + PIN[:16])
SCENARIOS = ("missing_client", "partial_frame", "oversized_frame", "wrong_owner_identity")

# The real engineering process supplies the fixture guardian role. A synthetic SID is only
# an expected-owner test alias; no account, token or privilege is acquired.
CHILD = r"""
import base64, ctypes, json, os, subprocess, sys, time
from pathlib import Path
from ctypes import wintypes
from security.windows_guardian_request_pipe import GuardianRequestPipe
from security.windows_pipe_identity import NativePipeIdentity

mode = sys.argv[1]
api = NativePipeIdentity()
process_sid = api.read_process_identity()
expected_owner = sys.argv[2] if len(sys.argv) > 2 else "S-1-5-21-100-200-300-9999"
if len(sys.argv) > 3 and process_sid != sys.argv[3]:
    raise AssertionError("Configured guardian process identity mismatch")
if process_sid == expected_owner:
    raise RuntimeError("Engineering identity must differ from fixture owner alias")
pipe = GuardianRequestPipe(guardian_sid=process_sid, owner_sid=expected_owner)

class NeverPersist:
    calls = 0
    def handle(self, *args, **kwargs):
        self.calls += 1
        raise AssertionError("Failure path reached reference handler")

reference = NeverPersist()
client = None
expected = {"missing_client": TimeoutError, "partial_frame": TimeoutError,
            "oversized_frame": ValueError, "wrong_owner_identity": PermissionError}[mode]
try:
    if mode != "missing_client":
        frame = {"partial_frame": (100).to_bytes(4,"big")+b"{",
                 "oversized_frame": (4097).to_bytes(4,"big"),
                 "wrong_owner_identity": (2).to_bytes(4,"big")+b"{}"}[mode]
        payload = base64.b64encode(frame).decode()
        command = (
            "$ErrorActionPreference='Stop';"
            "$rights=[IO.Pipes.PipeAccessRights]::ReadData -bor [IO.Pipes.PipeAccessRights]::WriteData -bor [IO.Pipes.PipeAccessRights]::ReadAttributes -bor [IO.Pipes.PipeAccessRights]::Synchronize;"
            "$client=[IO.Pipes.NamedPipeClientStream]::new('.', '"+pipe.name+"', $rights,[IO.Pipes.PipeOptions]::None,[Security.Principal.TokenImpersonationLevel]::Identification,[IO.HandleInheritability]::None);"
            "try{$client.Connect(2000);$data=[Convert]::FromBase64String('"+payload+"');"
            "$client.Write($data,0,$data.Length);Write-Output 'FRAME_SENT';Start-Sleep -Seconds 3}finally{$client.Dispose()}"
        )
        powershell = Path(os.environ['SystemRoot']) / 'System32' / 'WindowsPowerShell' / 'v1.0' / 'powershell.exe'
        if not powershell.is_absolute() or not powershell.is_file():
            raise AssertionError("Absolute Windows PowerShell executable unavailable")
        client = subprocess.Popen([str(powershell),"-NoProfile","-NonInteractive","-Command",command],
            stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True,
            creationflags=subprocess.CREATE_NO_WINDOW)
    started = time.monotonic()
    try:
        pipe.register_one(reference, timeout_seconds=0.15 if mode == "missing_client" else 1.5)
    except expected as exc:
        if mode == "wrong_owner_identity" and "Only configured owner" not in str(exc):
            raise AssertionError("Wrong identity rejection reason")
        if mode == "oversized_frame" and "frame" not in str(exc):
            raise AssertionError("Wrong frame rejection reason")
    else:
        raise AssertionError("Failure path was accepted")
    elapsed = time.monotonic()-started
    if elapsed > 3 or pipe.handle is not None or reference.calls:
        raise AssertionError("Failure path did not close without persistence")
    token = wintypes.HANDLE()
    if api.security.OpenThreadToken(api.kernel.GetCurrentThread(),8,True,ctypes.byref(token)):
        api.kernel.CloseHandle(token)
        raise AssertionError("Server retained an impersonation token")
    if ctypes.get_last_error() != 1008:
        raise AssertionError("Cannot establish restored server thread identity")
    if api.read_process_identity() != process_sid:
        raise AssertionError("Process identity changed")
finally:
    pipe.close()
    if client:
        try:
            out, err = client.communicate(timeout=4)
        except subprocess.TimeoutExpired:
            client.kill()
            client.communicate(timeout=3)
            raise AssertionError("Fixture client did not exit within its bounded lifetime")
        if "FRAME_SENT" not in out or err.strip():
            raise AssertionError("Client did not establish the required sent-frame control")
print(json.dumps({"scenario":mode,"passed":True,"reference_handler_calls":reference.calls,
    "pipe_closed":True,"no_thread_impersonation_token":True,"elapsed_seconds":round(elapsed,3),
    "execution_available":False,"reset_performed":False,"trial_started":False}))
"""


def verify_installed_payloads():
    raw = (RELEASE / "guardian-release.json").read_bytes()
    if hashlib.sha256(raw).hexdigest() != PIN:
        raise ValueError("Installed guardian manifest changed")
    manifest = json.loads(raw)
    for name, digest in manifest["files"].items():
        if hashlib.sha256((RELEASE / name).read_bytes()).hexdigest() != digest:
            raise ValueError("Installed guardian payload changed")


def check(*, environment=None):
    verify_installed_payloads()
    results = []
    for scenario in SCENARIOS:
        completed = subprocess.run(
            [str(RELEASE / "python.exe"), "-I", "-B", "-c", CHILD, scenario],
            capture_output=True,
            text=True,
            env=environment,
            timeout=8,
            check=False,
            creationflags=subprocess.CREATE_NO_WINDOW,
        )
        if completed.returncode or completed.stderr.strip():
            raise RuntimeError(
                f"Installed failure-path check failed: {scenario}: {completed.stderr}"
            )
        result = json.loads(completed.stdout)
        if result["scenario"] != scenario or result["passed"] is not True:
            raise RuntimeError("Failure-path result mismatch")
        results.append(result)
    return {
        "schema_version": "guardian-installed-engineering-failure-paths-v1",
        "observed_at_utc": datetime.now(UTC).isoformat(),
        "installed_manifest_sha256": PIN,
        "process_scope": "ENGINEERING_IDENTITY_WITH_FIXTURE_GUARDIAN_OWNER_ROLE_ALIASES",
        "scenarios": results,
        "actual_guardian_account_lifecycle_qualified": False,
        "other_identity_against_actual_guardian_qualified": False,
        "service_deployed": False,
        "execution_available": False,
        "reset_performed": False,
        "trial_started": False,
    }


if __name__ == "__main__":
    print(json.dumps(check(), indent=2))
