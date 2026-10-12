"""Single-use local diagnostic request transport; no broker or reset service."""

import ctypes
import math
import os
import re
import time
from contextlib import contextmanager
from ctypes import wintypes
from uuid import uuid4

from security.webull_pipe_registration import register_connected_request
from security.windows_pipe_identity import NativePipeIdentity


class _SecurityAttributes(ctypes.Structure):
    _fields_ = [
        ("length", wintypes.DWORD),
        ("descriptor", ctypes.c_void_p),
        ("inherit", wintypes.BOOL),
    ]


class _Overlapped(ctypes.Structure):
    _fields_ = [
        ("internal", ctypes.c_size_t),
        ("internal_high", ctypes.c_size_t),
        ("offset", wintypes.DWORD),
        ("offset_high", wintypes.DWORD),
        ("event", wintypes.HANDLE),
    ]


class LocalRequestPipe:
    def __init__(self, *, owner_sid, runtime_sid):
        if (
            not all(
                isinstance(s, str) and re.fullmatch(r"S-1-(?:[0-9]+-)*[0-9]+", s)
                for s in (owner_sid, runtime_sid)
            )
            or owner_sid == runtime_sid
        ):
            raise ValueError("Distinct protected identities required")
        self.api = NativePipeIdentity()
        self.owner_sid, self.runtime_sid = owner_sid, runtime_sid
        if self.api.read_process_identity() != owner_sid:
            raise PermissionError("Configured owner must match server process identity")
        self.name, self.handle, self.used = "AgenticRequest-" + uuid4().hex, None, False
        k, s = self.api.kernel, self.api.security
        declarations = [
            (
                k.CreateNamedPipeW,
                [
                    wintypes.LPCWSTR,
                    wintypes.DWORD,
                    wintypes.DWORD,
                    wintypes.DWORD,
                    wintypes.DWORD,
                    wintypes.DWORD,
                    wintypes.DWORD,
                    ctypes.POINTER(_SecurityAttributes),
                ],
                wintypes.HANDLE,
            ),
            (
                k.CreateEventW,
                [ctypes.c_void_p, wintypes.BOOL, wintypes.BOOL, wintypes.LPCWSTR],
                wintypes.HANDLE,
            ),
            (k.ConnectNamedPipe, [wintypes.HANDLE, ctypes.POINTER(_Overlapped)], wintypes.BOOL),
            (
                k.ReadFile,
                [
                    wintypes.HANDLE,
                    ctypes.c_void_p,
                    wintypes.DWORD,
                    ctypes.POINTER(wintypes.DWORD),
                    ctypes.POINTER(_Overlapped),
                ],
                wintypes.BOOL,
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
            (k.DisconnectNamedPipe, [wintypes.HANDLE], wintypes.BOOL),
            (
                s.ConvertStringSecurityDescriptorToSecurityDescriptorW,
                [
                    wintypes.LPCWSTR,
                    wintypes.DWORD,
                    ctypes.POINTER(ctypes.c_void_p),
                    ctypes.POINTER(wintypes.DWORD),
                ],
                wintypes.BOOL,
            ),
            (
                s.GetSecurityDescriptorSacl,
                [
                    ctypes.c_void_p,
                    ctypes.POINTER(wintypes.BOOL),
                    ctypes.POINTER(ctypes.c_void_p),
                    ctypes.POINTER(wintypes.BOOL),
                ],
                wintypes.BOOL,
            ),
            (
                s.SetSecurityInfo,
                [
                    wintypes.HANDLE,
                    wintypes.DWORD,
                    wintypes.DWORD,
                    ctypes.c_void_p,
                    ctypes.c_void_p,
                    ctypes.c_void_p,
                    ctypes.c_void_p,
                ],
                wintypes.DWORD,
            ),
            (
                s.GetSecurityInfo,
                [
                    wintypes.HANDLE,
                    wintypes.DWORD,
                    wintypes.DWORD,
                    ctypes.POINTER(ctypes.c_void_p),
                    ctypes.POINTER(ctypes.c_void_p),
                    ctypes.POINTER(ctypes.c_void_p),
                    ctypes.POINTER(ctypes.c_void_p),
                    ctypes.POINTER(ctypes.c_void_p),
                ],
                wintypes.DWORD,
            ),
            (
                s.ConvertSecurityDescriptorToStringSecurityDescriptorW,
                [
                    ctypes.c_void_p,
                    wintypes.DWORD,
                    wintypes.DWORD,
                    ctypes.POINTER(wintypes.LPWSTR),
                    ctypes.POINTER(wintypes.DWORD),
                ],
                wintypes.BOOL,
            ),
        ]
        for function, arguments, result in declarations:
            function.argtypes, function.restype = arguments, result
        try:
            descriptor = f"O:{owner_sid}D:P(A;;GA;;;{owner_sid})(A;;0x100083;;;{runtime_sid})"
            with self._descriptor(descriptor) as sd:
                attributes = _SecurityAttributes(ctypes.sizeof(_SecurityAttributes), sd, False)
                # OVERLAPPED, FIRST_PIPE_INSTANCE/WRITE_OWNER, duplex; remote rejection.
                self.handle = k.CreateNamedPipeW(
                    "\\\\.\\pipe\\" + self.name,
                    0x40080003,
                    8,
                    1,
                    4100,
                    4100,
                    1000,
                    ctypes.byref(attributes),
                )
            if not self.handle or self.handle == ctypes.c_void_p(-1).value:
                self.handle = None
                raise OSError("Local request pipe creation failed")
            with self._descriptor("S:(ML;;NW;;;ME)") as sd:
                present, defaulted, acl = wintypes.BOOL(), wintypes.BOOL(), ctypes.c_void_p()
                if (
                    not s.GetSecurityDescriptorSacl(
                        sd, ctypes.byref(present), ctypes.byref(acl), ctypes.byref(defaulted)
                    )
                    or not present.value
                ):
                    raise OSError("Pipe integrity descriptor unavailable")
                if s.SetSecurityInfo(self.handle, 6, 16, None, None, None, acl) != 0:
                    raise OSError("Pipe medium integrity setting failed")
            if self._security_text(16) != "S:(ML;;NW;;;ME)":
                raise OSError("Pipe medium integrity readback failed")
            expected = f"O:{owner_sid}D:P(A;;FA;;;{owner_sid})(A;;0x100083;;;{runtime_sid})"
            if self._security_text(5) != expected:
                raise OSError("Pipe owner and protected permissions readback failed")
        except BaseException:
            self.close()
            raise

    @contextmanager
    def _descriptor(self, text):
        sd, size = ctypes.c_void_p(), wintypes.DWORD()
        if not self.api.security.ConvertStringSecurityDescriptorToSecurityDescriptorW(
            text, 1, ctypes.byref(sd), ctypes.byref(size)
        ):
            raise OSError("Pipe security descriptor invalid")
        try:
            yield sd
        finally:
            self.api.kernel.LocalFree(sd)

    def _security_text(self, info):
        pointers = [ctypes.c_void_p() for _ in range(5)]
        if (
            self.api.security.GetSecurityInfo(
                self.handle, 6, info, *(ctypes.byref(p) for p in pointers)
            )
            != 0
        ):
            raise OSError("Pipe security readback unavailable")
        sd = pointers[-1]
        try:
            text, size = wintypes.LPWSTR(), wintypes.DWORD()
            if not self.api.security.ConvertSecurityDescriptorToStringSecurityDescriptorW(
                sd, 1, info, ctypes.byref(text), ctypes.byref(size)
            ):
                raise OSError("Pipe security conversion failed")
            try:
                return text.value
            finally:
                self.api.kernel.LocalFree(ctypes.cast(text, ctypes.c_void_p))
        finally:
            self.api.kernel.LocalFree(sd)

    def _operation(self, invoke, deadline, *, connecting=False):
        k = self.api.kernel
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            raise TimeoutError("Request transport deadline exceeded")
        event = k.CreateEventW(None, True, False, None)
        if not event:
            raise OSError("Pipe event creation failed")
        operation, count = _Overlapped(event=event), wintypes.DWORD()
        pending = False
        try:
            succeeded = invoke(operation, count)
            error = ctypes.get_last_error() if not succeeded else 0
            if connecting and error == 535:
                return 0
            if not succeeded and error != 997:
                raise OSError("Request pipe operation failed")
            if not succeeded:
                pending = True
                wait = k.WaitForSingleObject(event, max(1, math.ceil(remaining * 1000)))
                if wait != 0:
                    raise TimeoutError("Request transport deadline exceeded")
                pending = False
            if not k.GetOverlappedResult(
                self.handle, ctypes.byref(operation), ctypes.byref(count), False
            ):
                raise OSError("Request pipe completion failed")
            return count.value
        finally:
            if pending:
                k.CancelIoEx(self.handle, ctypes.byref(operation))
                # Also drain on interruption: buffers/OVERLAPPED must stay alive.
                if k.WaitForSingleObject(event, 1000) != 0:
                    os._exit(71)
            k.CloseHandle(event)

    def _read_exact(self, size, deadline):
        result = bytearray()
        while len(result) < size:
            buffer = ctypes.create_string_buffer(size - len(result))
            count = self._operation(
                lambda op, count, buffer=buffer: self.api.kernel.ReadFile(
                    self.handle, buffer, len(buffer), ctypes.byref(count), ctypes.byref(op)
                ),
                deadline,
            )
            if not 0 < count <= len(buffer):
                raise OSError("Request pipe closed or invalid read")
            result.extend(buffer.raw[:count])
        return bytes(result)

    def register_one(self, journal, *, timeout_seconds=5):
        if (
            type(timeout_seconds) not in (int, float)
            or not math.isfinite(timeout_seconds)
            or not 0 < timeout_seconds <= 5
        ):
            raise ValueError("Transport deadline must be positive and at most five seconds")
        if self.used or self.handle is None:
            raise ValueError("Single-use request pipe unavailable")
        self.used = True
        deadline = time.monotonic() + timeout_seconds
        try:
            self._operation(
                lambda op, count: self.api.kernel.ConnectNamedPipe(self.handle, ctypes.byref(op)),
                deadline,
                connecting=True,
            )
            length = int.from_bytes(self._read_exact(4, deadline), "big")
            if not 1 <= length <= 4096:
                raise ValueError("Request frame exceeds allowed size")
            raw = self._read_exact(length, deadline)
            return self._dispatch(raw, journal)
        finally:
            self.close()

    def _dispatch(self, raw, journal):
        return register_connected_request(
            self.handle,
            raw,
            journal,
            owner_sid=self.owner_sid,
            runtime_sid=self.runtime_sid,
            identity_api=self.api,
        )

    def close(self):
        if self.handle is not None:
            self.api.kernel.DisconnectNamedPipe(self.handle)
            self.api.kernel.CloseHandle(self.handle)
            self.handle = None
