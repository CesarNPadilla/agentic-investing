"""Identify the last-read local pipe client; restore server identity before returning."""

import ctypes
import os
from ctypes import wintypes


class _SidAndAttributes(ctypes.Structure):
    _fields_ = [("sid", ctypes.c_void_p), ("attributes", wintypes.DWORD)]


class NativePipeIdentity:
    def __init__(self):
        if os.name != "nt":
            raise OSError("Windows pipe identity required")
        self.security = ctypes.WinDLL("advapi32", use_last_error=True)
        self.kernel = ctypes.WinDLL("kernel32", use_last_error=True)
        declarations = [
            (self.security.ImpersonateNamedPipeClient, [wintypes.HANDLE], wintypes.BOOL),
            (self.security.RevertToSelf, [], wintypes.BOOL),
            (
                self.security.OpenThreadToken,
                [wintypes.HANDLE, wintypes.DWORD, wintypes.BOOL, ctypes.POINTER(wintypes.HANDLE)],
                wintypes.BOOL,
            ),
            (
                self.security.GetTokenInformation,
                [
                    wintypes.HANDLE,
                    ctypes.c_int,
                    ctypes.c_void_p,
                    wintypes.DWORD,
                    ctypes.POINTER(wintypes.DWORD),
                ],
                wintypes.BOOL,
            ),
            (
                self.security.ConvertSidToStringSidW,
                [ctypes.c_void_p, ctypes.POINTER(wintypes.LPWSTR)],
                wintypes.BOOL,
            ),
            (self.kernel.GetCurrentThread, [], wintypes.HANDLE),
            (self.kernel.GetCurrentProcess, [], wintypes.HANDLE),
            (
                self.security.OpenProcessToken,
                [wintypes.HANDLE, wintypes.DWORD, ctypes.POINTER(wintypes.HANDLE)],
                wintypes.BOOL,
            ),
            (self.kernel.CloseHandle, [wintypes.HANDLE], wintypes.BOOL),
            (self.kernel.LocalFree, [ctypes.c_void_p], ctypes.c_void_p),
        ]
        for function, arguments, result in declarations:
            function.argtypes, function.restype = arguments, result

    def impersonate(self, handle):
        return bool(self.security.ImpersonateNamedPipeClient(handle))

    def revert(self):
        return bool(self.security.RevertToSelf())

    def read_identity(self):
        token = wintypes.HANDLE()
        if not self.security.OpenThreadToken(
            self.kernel.GetCurrentThread(), 8, True, ctypes.byref(token)
        ):
            raise OSError("Pipe client token unavailable")
        try:
            size = wintypes.DWORD()
            level = wintypes.DWORD()
            if (
                not self.security.GetTokenInformation(
                    token, 9, ctypes.byref(level), ctypes.sizeof(level), ctypes.byref(size)
                )
                or level.value < 1
            ):
                raise OSError("Identifiable client token required")
            return self._token_sid(token)
        finally:
            self.kernel.CloseHandle(token)

    def read_process_identity(self):
        token = wintypes.HANDLE()
        if not self.security.OpenProcessToken(
            self.kernel.GetCurrentProcess(), 8, ctypes.byref(token)
        ):
            raise OSError("Server process identity unavailable")
        try:
            return self._token_sid(token)
        finally:
            self.kernel.CloseHandle(token)

    def _token_sid(self, token):
        size = wintypes.DWORD()
        self.security.GetTokenInformation(token, 1, None, 0, ctypes.byref(size))
        if not 0 < size.value <= 65536:
            raise OSError("Token size invalid")
        buffer = ctypes.create_string_buffer(size.value)
        if not self.security.GetTokenInformation(token, 1, buffer, size.value, ctypes.byref(size)):
            raise OSError("Token identity unavailable")
        user = ctypes.cast(buffer, ctypes.POINTER(_SidAndAttributes)).contents
        text = wintypes.LPWSTR()
        if not self.security.ConvertSidToStringSidW(user.sid, ctypes.byref(text)):
            raise OSError("Identity conversion failed")
        try:
            return text.value
        finally:
            self.kernel.LocalFree(ctypes.cast(text, ctypes.c_void_p))


def identify_pipe_client(handle, *, api=None, terminate=os._exit):
    """Only call after reading a message from a connected server-side pipe handle.

    Never perform persistence or broker work while impersonating. Reversion failure
    terminates the dedicated controller process rather than continuing under a client.
    """
    api = api or NativePipeIdentity()
    if not api.impersonate(handle):
        raise OSError("Pipe client authentication failed")
    try:
        sid = api.read_identity()
        if not isinstance(sid, str) or not sid.startswith("S-1-"):
            raise OSError("Pipe client identity invalid")
        return sid
    finally:
        if not api.revert():
            terminate(70)
            raise RuntimeError("Fatal identity reversion failure")
