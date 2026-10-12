"""Staged owner client: authenticate the pipe server before sending signed evidence."""

import ctypes
import json
import math
import re
import time
from ctypes import wintypes

from security.windows_local_request_pipe import LocalRequestPipe, _Overlapped
from security.windows_pipe_identity import NativePipeIdentity


class GuardianExchangeClient(LocalRequestPipe):
    def __init__(self, *, name, guardian_sid):
        if not isinstance(name, str) or not re.fullmatch(r"AgenticRequest-[0-9a-f]{32}", name):
            raise ValueError("Protected local pipe name required")
        if not isinstance(guardian_sid, str) or not re.fullmatch(
            r"S-1-(?:[0-9]+-)*[0-9]+", guardian_sid
        ):
            raise ValueError("Configured guardian identity required")
        self.name, self.guardian_sid = name, guardian_sid
        self.handle, self.used = None, False
        self.api = NativePipeIdentity()
        k = self.api.kernel
        io = [
            wintypes.HANDLE,
            ctypes.c_void_p,
            wintypes.DWORD,
            ctypes.POINTER(wintypes.DWORD),
            ctypes.POINTER(_Overlapped),
        ]
        declarations = [
            (
                k.CreateFileW,
                [
                    wintypes.LPCWSTR,
                    wintypes.DWORD,
                    wintypes.DWORD,
                    ctypes.c_void_p,
                    wintypes.DWORD,
                    wintypes.DWORD,
                    wintypes.HANDLE,
                ],
                wintypes.HANDLE,
            ),
            (
                k.GetNamedPipeServerProcessId,
                [wintypes.HANDLE, ctypes.POINTER(wintypes.ULONG)],
                wintypes.BOOL,
            ),
            (k.OpenProcess, [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD], wintypes.HANDLE),
            (k.ReadFile, io, wintypes.BOOL),
            (k.WriteFile, io, wintypes.BOOL),
            (
                k.CreateEventW,
                [ctypes.c_void_p, wintypes.BOOL, wintypes.BOOL, wintypes.LPCWSTR],
                wintypes.HANDLE,
            ),
            (k.WaitForSingleObject, [wintypes.HANDLE, wintypes.DWORD], wintypes.DWORD),
            (
                k.GetOverlappedResult,
                [
                    wintypes.HANDLE,
                    ctypes.POINTER(_Overlapped),
                    ctypes.POINTER(wintypes.DWORD),
                    wintypes.BOOL,
                ],
                wintypes.BOOL,
            ),
            (k.CancelIoEx, [wintypes.HANDLE, ctypes.POINTER(_Overlapped)], wintypes.BOOL),
        ]
        for function, arguments, result in declarations:
            function.argtypes, function.restype = arguments, result

    def _server_process(self):
        k = self.api.kernel
        pid = wintypes.ULONG()
        if not k.GetNamedPipeServerProcessId(self.handle, ctypes.byref(pid)) or not pid.value:
            raise OSError("Guardian server process unavailable")
        process = k.OpenProcess(0x1000, False, pid.value)
        if not process:
            raise OSError("Guardian server process query denied")
        token = wintypes.HANDLE()
        try:
            if not self.api.security.OpenProcessToken(process, 8, ctypes.byref(token)):
                raise OSError("Guardian server token query denied")
            if self.api._token_sid(token) != self.guardian_sid:
                raise PermissionError("Guardian server identity mismatch")
            return process
        except BaseException:
            k.CloseHandle(process)
            raise
        finally:
            if token:
                k.CloseHandle(token)

    def _write(self, raw, deadline):
        offset = 0
        while offset < len(raw):
            buffer = ctypes.create_string_buffer(raw[offset:])
            remaining = len(raw) - offset
            count = self._operation(
                lambda op, count, buffer=buffer, remaining=remaining: self.api.kernel.WriteFile(
                    self.handle, buffer, remaining, ctypes.byref(count), ctypes.byref(op)
                ),
                deadline,
            )
            if not 0 < count <= remaining:
                raise OSError("Guardian client write failed")
            offset += count

    def exchange(self, raw, *, timeout_seconds=5):
        if type(raw) is not bytes or not 1 <= len(raw) <= 4096:
            raise ValueError("Bounded guardian request required")
        if (
            type(timeout_seconds) not in (int, float)
            or not math.isfinite(timeout_seconds)
            or not 0 < timeout_seconds <= 5
        ):
            raise ValueError("Bounded guardian deadline required")
        if self.used:
            raise ValueError("Single-use guardian client already used")
        self.used = True
        deadline = time.monotonic() + timeout_seconds
        process = None
        try:
            # Overlapped IO; explicit impersonation SQOS; no host from request data.
            self.handle = self.api.kernel.CreateFileW(
                "\\\\.\\pipe\\" + self.name, 0x100083, 0, None, 3, 0x40120000, None
            )
            if not self.handle or self.handle == ctypes.c_void_p(-1).value:
                self.handle = None
                raise OSError("Guardian local pipe unavailable")
            process = self._server_process()
            self._write(len(raw).to_bytes(4, "big") + raw, deadline)
            size = int.from_bytes(self._read_exact(4, deadline), "big")
            if not 1 <= size <= 4096:
                raise ValueError("Guardian reply size rejected")

            def unique(pairs):
                result = {}
                for key, value in pairs:
                    if key in result:
                        raise ValueError("Duplicate guardian reply key")
                    result[key] = value
                return result

            def reject_constant(_):
                raise ValueError("Nonfinite guardian reply")

            response = json.loads(
                self._read_exact(size, deadline).decode("utf-8"),
                object_pairs_hook=unique,
                parse_constant=reject_constant,
            )
            if type(response) is not dict:
                raise ValueError("Guardian reply object required")
            self._write(b"\x01", deadline)
            return response
        finally:
            self.close()
            if process:
                self.api.kernel.CloseHandle(process)

    def close(self):
        if self.handle is not None:
            self.api.kernel.CloseHandle(self.handle)
            self.handle = None
