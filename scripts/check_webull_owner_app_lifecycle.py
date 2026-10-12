"""Bounded installed-app diagnostic with absent private state; no owner ceremony."""

import argparse
import ctypes
import hashlib
import http.client
import json
import os
import socket
import subprocess
import time
import uuid
from ctypes import wintypes
from datetime import UTC, datetime
from pathlib import Path

ENVIRONMENT = Path(
    r"C:\ProgramData\AgenticInvestingPaper\OwnerControl\WebullReviewEnvironment-f2eb1b3b90ce7a79"
)
MANIFEST_SHA256 = "f2eb1b3b90ce7a79346ab72189ced4f59eda14ac9c89ddccda2139cc74cbd33b"


def request(path, method="GET", *, host="localhost:8767", origin=None):
    connection = http.client.HTTPConnection("127.0.0.1", 8767, timeout=2)
    headers = {"Host": host}
    if origin is not None:
        headers["Origin"] = origin
    try:
        connection.request(method, path, body=b"{}" if method == "POST" else None, headers=headers)
        response = connection.getresponse()
        body = response.read(100000)
        return response.status, dict(response.getheaders()), body
    finally:
        connection.close()


def require_standard_owner(expected_sid):
    security = ctypes.WinDLL("advapi32", use_last_error=True)
    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel.GetCurrentProcess.restype = wintypes.HANDLE
    security.OpenProcessToken.argtypes = [
        wintypes.HANDLE,
        wintypes.DWORD,
        ctypes.POINTER(wintypes.HANDLE),
    ]
    security.GetTokenInformation.argtypes = [
        wintypes.HANDLE,
        ctypes.c_int,
        ctypes.c_void_p,
        wintypes.DWORD,
        ctypes.POINTER(wintypes.DWORD),
    ]
    security.ConvertSidToStringSidW.argtypes = [ctypes.c_void_p, ctypes.POINTER(wintypes.LPWSTR)]
    kernel.LocalFree.argtypes = [ctypes.c_void_p]
    kernel.CloseHandle.argtypes = [wintypes.HANDLE]
    token, size, elevation = wintypes.HANDLE(), wintypes.DWORD(), wintypes.DWORD()
    if not security.OpenProcessToken(kernel.GetCurrentProcess(), 8, ctypes.byref(token)):
        raise OSError("Owner process token unavailable")
    try:
        if (
            not security.GetTokenInformation(
                token, 20, ctypes.byref(elevation), 4, ctypes.byref(size)
            )
            or elevation.value
        ):
            raise PermissionError("Non-elevated owner process required")
        security.GetTokenInformation(token, 1, None, 0, ctypes.byref(size))
        if not 0 < size.value <= 65536:
            raise OSError("Owner token identity size rejected")
        buffer = ctypes.create_string_buffer(size.value)
        if not security.GetTokenInformation(token, 1, buffer, size.value, ctypes.byref(size)):
            raise OSError("Owner token identity unavailable")
        sid_pointer = ctypes.cast(buffer, ctypes.POINTER(ctypes.c_void_p)).contents.value
        text = wintypes.LPWSTR()
        if not security.ConvertSidToStringSidW(sid_pointer, ctypes.byref(text)):
            raise OSError("Owner token identity conversion failed")
        try:
            if text.value != expected_sid:
                raise PermissionError("Configured owner identity mismatch")
        finally:
            kernel.LocalFree(ctypes.cast(text, ctypes.c_void_p))
    finally:
        kernel.CloseHandle(token)


def check(*, standard_owner_sid=None):
    if standard_owner_sid is not None:
        require_standard_owner(standard_owner_sid)
    # Exclusive loopback bind preflight: never probe/terminate an existing listener.
    with socket.socket() as preflight:
        preflight.setsockopt(socket.SOL_SOCKET, socket.SO_EXCLUSIVEADDRUSE, 1)
        preflight.bind(("127.0.0.1", 8767))
    repo = Path(__file__).resolve().parents[1]
    powershell = Path(os.environ["SystemRoot"]) / "System32/WindowsPowerShell/v1.0/powershell.exe"
    subprocess.run(
        [
            str(powershell),
            "-NoProfile",
            "-NonInteractive",
            "-File",
            str(repo / "scripts/audit_webull_review_source.ps1"),
            "-InstalledDirectory",
            r"C:\ProgramData\AgenticInvestingPaper\OwnerControl\WebullReviewSource-3f83d3a65cead1c1",
            "-ExpectedManifestSha256",
            "3f83d3a65cead1c1aa1ca0d9446df741694fc520470ed6b65d140f9eb5e0ad43",
        ],
        check=True,
        capture_output=True,
        timeout=45,
    )
    subprocess.run(
        [
            str(powershell),
            "-NoProfile",
            "-NonInteractive",
            "-File",
            str(repo / "scripts/audit_webull_review_environment.ps1"),
            "-InstalledDirectory",
            str(ENVIRONMENT),
            "-ExpectedManifestSha256",
            MANIFEST_SHA256,
        ],
        check=True,
        capture_output=True,
        timeout=45,
    )
    run = (
        Path(os.environ["LOCALAPPDATA"])
        / "AgenticInvesting/staging"
        / ("owner-app-lifecycle-" + uuid.uuid4().hex)
    )
    run.mkdir()
    paths = [
        run / name
        for name in ("absent-credential.json", "absent-envelope.json", "absent-journal.db")
    ]
    environment = {
        "SystemRoot": os.environ["SystemRoot"],
        "WINDIR": os.environ["SystemRoot"],
        "PATH": str(Path(os.environ["SystemRoot"]) / "System32"),
        "TEMP": str(run),
        "TMP": str(run),
    }
    observations = []
    with (run / "stdout.txt").open("wb") as stdout, (run / "stderr.txt").open("wb") as stderr:
        process = subprocess.Popen(
            [
                str(ENVIRONMENT / "python.exe"),
                "-I",
                "-B",
                "-m",
                "security.webull_owner_review_app",
                "--credential-file",
                str(paths[0]),
                "--envelope-file",
                str(paths[1]),
                "--journal-file",
                str(paths[2]),
            ],
            cwd=run,
            env=environment,
            stdout=stdout,
            stderr=stderr,
            creationflags=subprocess.CREATE_NO_WINDOW,
        )
        try:
            deadline = time.monotonic() + 10
            while True:
                if process.poll() is not None:
                    raise RuntimeError("Installed app exited during startup; retained diagnostics")
                try:
                    status, _, _ = request("/")
                    if status == 200:
                        break
                except OSError:
                    pass
                if time.monotonic() >= deadline:
                    raise TimeoutError("Installed app startup exceeded 10 seconds")
                time.sleep(0.1)
            cases = [
                ("page", "/", "GET", "localhost:8767", None, 200),
                ("javascript", "/owner.js", "GET", "localhost:8767", None, 200),
                ("missing_review", "/review", "GET", "localhost:8767", None, 409),
                ("missing_begin", "/begin", "POST", "localhost:8767", "http://localhost:8767", 409),
                (
                    "no_challenge",
                    "/complete",
                    "POST",
                    "localhost:8767",
                    "http://localhost:8767",
                    403,
                ),
                ("wrong_host", "/review", "GET", "invalid.local:8767", None, 403),
                ("wrong_origin", "/begin", "POST", "localhost:8767", "http://invalid.local", 403),
                ("absent_origin", "/begin", "POST", "localhost:8767", None, 403),
                ("no_openapi", "/openapi.json", "GET", "localhost:8767", None, 404),
                ("no_docs", "/docs", "GET", "localhost:8767", None, 404),
            ]
            for name, path, method, host, origin, expected in cases:
                status, headers, _ = request(path, method, host=host, origin=origin)
                if status != expected or "set-cookie" in {key.lower() for key in headers}:
                    raise AssertionError(f"Request check failed: {name}")
                if (
                    host == "localhost:8767"
                    and (method == "GET" or origin == "http://localhost:8767")
                    and (
                        headers.get("cache-control") != "no-store"
                        or headers.get("x-frame-options") != "DENY"
                    )
                ):
                    raise AssertionError(f"Response boundary failed: {name}")
                observations.append({"case": name, "status": status})
        finally:
            if process.poll() is None:
                process.terminate()
            process.wait(timeout=5)
    if any(path.exists() for path in paths):
        raise AssertionError("Diagnostic created private review state")
    with socket.socket() as closed:
        closed.settimeout(1)
        if closed.connect_ex(("127.0.0.1", 8767)) == 0:
            raise AssertionError("Listener remains after child termination")
    result = {
        "observed_at": datetime.now(UTC).isoformat(),
        "scope": (
            "INSTALLED_OWNER_APP_STANDARD_OWNER_TOKEN_MISSING_STATE_FORCED_PROCESS_SHUTDOWN"
            if standard_owner_sid is not None
            else "INSTALLED_OWNER_APP_ENGINEERING_TOKEN_MISSING_STATE_FORCED_PROCESS_SHUTDOWN"
        ),
        "checks": observations,
        "private_state_created": False,
        "listener_closed": True,
        "standard_owner_token_qualified": standard_owner_sid is not None,
        "graceful_shutdown_qualified": False,
        "guardian_integration_qualified": False,
        "execution_available": False,
        "reset_authorized": False,
        "trial_started": False,
        "script_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
    }
    (run / "result.json").write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    return run / "result.json"


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--standard-owner-sid")
    args = parser.parse_args()
    print(check(standard_owner_sid=args.standard_owner_sid))
