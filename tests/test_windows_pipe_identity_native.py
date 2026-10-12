"""Disposable local same-identity pipe; no service, credentials or broker calls."""

import ctypes
import subprocess
import time
from ctypes import wintypes
from uuid import uuid4

from security.windows_pipe_identity import NativePipeIdentity, identify_pipe_client


def test_actual_identification_token_and_server_reversion():
    api = NativePipeIdentity()
    kernel = api.kernel
    kernel.CreateNamedPipeW.argtypes = [
        wintypes.LPCWSTR,
        wintypes.DWORD,
        wintypes.DWORD,
        wintypes.DWORD,
        wintypes.DWORD,
        wintypes.DWORD,
        wintypes.DWORD,
        ctypes.c_void_p,
    ]
    kernel.CreateNamedPipeW.restype = wintypes.HANDLE
    kernel.ConnectNamedPipe.argtypes = [wintypes.HANDLE, ctypes.c_void_p]
    kernel.ConnectNamedPipe.restype = wintypes.BOOL
    kernel.ReadFile.argtypes = [
        wintypes.HANDLE,
        ctypes.c_void_p,
        wintypes.DWORD,
        ctypes.POINTER(wintypes.DWORD),
        ctypes.c_void_p,
    ]
    kernel.ReadFile.restype = wintypes.BOOL
    name = "AgenticDiagnostic-" + uuid4().hex
    # First instance, byte mode, nonblocking, local clients only. Default owner ACL
    # is used solely for this same-identity fixture, never as a deployment policy.
    pipe = kernel.CreateNamedPipeW(
        "\\\\.\\pipe\\" + name, 3 | 0x80000, 1 | 8, 1, 4096, 4096, 1000, None
    )
    assert pipe and pipe != ctypes.c_void_p(-1).value
    process = None
    try:
        code = (
            "$ErrorActionPreference='Stop';"
            "$pipe=New-Object System.IO.Pipes.NamedPipeClientStream('.', '"
            + name
            + "', [System.IO.Pipes.PipeDirection]::InOut, [System.IO.Pipes.PipeOptions]::None,"
            "[System.Security.Principal.TokenImpersonationLevel]::Identification);"
            "$pipe.Connect(3000);$pipe.WriteByte(1);$pipe.Flush();Start-Sleep -Seconds 6;$pipe.Dispose()"
        )
        process = subprocess.Popen(
            ["powershell.exe", "-NoProfile", "-NonInteractive", "-Command", code],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            creationflags=subprocess.CREATE_NO_WINDOW,
        )
        deadline = time.monotonic() + 5
        connected = False
        while time.monotonic() < deadline and process.poll() is None:
            if kernel.ConnectNamedPipe(pipe, None) or ctypes.get_last_error() == 535:
                connected = True
                break
            time.sleep(0.02)
        assert connected, "Local diagnostic client did not connect"
        buffer = ctypes.create_string_buffer(1)
        read = wintypes.DWORD()
        while time.monotonic() < deadline and process.poll() is None:
            if kernel.ReadFile(pipe, buffer, 1, ctypes.byref(read), None) and read.value == 1:
                break
            time.sleep(0.02)
        assert read.value == 1, "Client message must precede identity inspection"
        sid = identify_pipe_client(pipe, api=api)
        assert sid.startswith("S-1-"), "Native client identity unavailable"
        token = wintypes.HANDLE()
        opened = api.security.OpenThreadToken(
            kernel.GetCurrentThread(), 8, True, ctypes.byref(token)
        )
        if opened:
            kernel.CloseHandle(token)
        assert not opened and ctypes.get_last_error() == 1008, "Server impersonation must end"
    finally:
        if process is not None and process.poll() is None:
            process.kill()
            process.wait(timeout=5)
        kernel.CloseHandle(pipe)
