"""Read administrator-protected configuration from held native handles; no activation."""

import ctypes
import os
import re
from ctypes import wintypes
from pathlib import PureWindowsPath

from security.webull_guardian_host_config import parse_pinned_host_config
from security.windows_pipe_identity import NativePipeIdentity

ROOT = PureWindowsPath(r"C:\ProgramData\AgenticInvestingGuardian")
ADMIN = "S-1-5-32-544"
SYSTEM = "S-1-5-18"


class ProtectedConfigReader:
    def __init__(self):
        if os.name != "nt":
            raise OSError("Native Windows configuration protection required")
        self.kernel = ctypes.WinDLL("kernel32", use_last_error=True)
        self.security = ctypes.WinDLL("advapi32", use_last_error=True)
        p = ctypes.c_void_p
        declarations = [
            (
                self.kernel.CreateFileW,
                [
                    wintypes.LPCWSTR,
                    wintypes.DWORD,
                    wintypes.DWORD,
                    p,
                    wintypes.DWORD,
                    wintypes.DWORD,
                    p,
                ],
                wintypes.HANDLE,
            ),
            (self.kernel.CloseHandle, [wintypes.HANDLE], wintypes.BOOL),
            (self.kernel.LocalFree, [p], p),
            (self.kernel.GetFileInformationByHandle, [wintypes.HANDLE, p], wintypes.BOOL),
            (
                self.kernel.GetFileSizeEx,
                [wintypes.HANDLE, ctypes.POINTER(ctypes.c_longlong)],
                wintypes.BOOL,
            ),
            (
                self.kernel.ReadFile,
                [wintypes.HANDLE, p, wintypes.DWORD, ctypes.POINTER(wintypes.DWORD), p],
                wintypes.BOOL,
            ),
            (
                self.security.GetSecurityInfo,
                [
                    wintypes.HANDLE,
                    ctypes.c_int,
                    wintypes.DWORD,
                    ctypes.POINTER(p),
                    p,
                    ctypes.POINTER(p),
                    p,
                    ctypes.POINTER(p),
                ],
                wintypes.DWORD,
            ),
            (
                self.security.GetSecurityDescriptorControl,
                [p, ctypes.POINTER(wintypes.WORD), ctypes.POINTER(wintypes.DWORD)],
                wintypes.BOOL,
            ),
            (self.security.GetAce, [p, wintypes.DWORD, ctypes.POINTER(p)], wintypes.BOOL),
            (self.security.ConvertSidToStringSidW, [p, ctypes.POINTER(p)], wintypes.BOOL),
        ]
        for function, arguments, result in declarations:
            function.argtypes, function.restype = arguments, result

    def _sid(self, pointer):
        value = ctypes.c_void_p()
        if not self.security.ConvertSidToStringSidW(pointer, ctypes.byref(value)):
            raise OSError("Security identity conversion failed")
        try:
            return ctypes.wstring_at(value)
        finally:
            self.kernel.LocalFree(value)

    def _check(self, handle, *, directory, owner_sid, guardian_sid):
        info = ctypes.create_string_buffer(52)
        if not self.kernel.GetFileInformationByHandle(handle, info):
            raise OSError("Protected file information unavailable")
        attrs = ctypes.c_uint32.from_buffer(info).value
        if attrs & 0x400 or bool(attrs & 0x10) != directory:
            raise ValueError("Ordinary configuration object required")
        if not directory and ctypes.c_uint32.from_buffer(info, 40).value != 1:
            raise ValueError("Single-link configuration required")
        owner, acl, descriptor = (ctypes.c_void_p() for _ in range(3))
        result = self.security.GetSecurityInfo(
            handle,
            1,
            5,
            ctypes.byref(owner),
            None,
            ctypes.byref(acl),
            None,
            ctypes.byref(descriptor),
        )
        if result:
            raise OSError("Configuration security descriptor unavailable")
        try:
            control, revision = wintypes.WORD(), wintypes.DWORD()
            if not self.security.GetSecurityDescriptorControl(
                descriptor, ctypes.byref(control), ctypes.byref(revision)
            ):
                raise OSError("Configuration security control unavailable")
            if not control.value & 0x1000 or self._sid(owner) != ADMIN or not acl:
                raise ValueError("Protected administrator-owned DACL required")
            count = ctypes.c_uint16.from_address(acl.value + 4).value
            expected = {
                ADMIN: 0x1F01FF,
                SYSTEM: 0x1F01FF,
                owner_sid: 0x1200A9,
                guardian_sid: 0x1200A9,
            }
            if len(expected) != 4 or count != 4:
                raise ValueError("Exactly four distinct protected roles required")
            seen = set()
            for index in range(count):
                ace = ctypes.c_void_p()
                if not self.security.GetAce(acl, index, ctypes.byref(ace)):
                    raise OSError("Configuration ACE unavailable")
                kind, flags = ctypes.string_at(ace, 2)
                mask = ctypes.c_uint32.from_address(ace.value + 4).value
                sid = self._sid(ace.value + 8)
                if (
                    kind != 0
                    or flags != (3 if directory else 0)
                    or sid in seen
                    or expected.get(sid) != mask
                ):
                    raise ValueError("Exact protected configuration ACL mismatch")
                seen.add(sid)
        finally:
            self.kernel.LocalFree(descriptor)

    def read(self, path, *, owner_sid, guardian_sid):
        return self._read(
            path,
            owner_sid=owner_sid,
            guardian_sid=guardian_sid,
            pattern=r"HostConfig-[0-9a-f]{32}\.json",
        )

    def read_registry(self, path, *, owner_sid, guardian_sid):
        return self._read(
            path,
            owner_sid=owner_sid,
            guardian_sid=guardian_sid,
            pattern=r"AcceptedOwnerCredential-[0-9a-f]{64}\.json",
        )

    def _read(self, path, *, owner_sid, guardian_sid, pattern):
        path = PureWindowsPath(path)
        if path.parent != ROOT / "Code" or not re.fullmatch(pattern, path.name):
            raise ValueError("Fixed protected configuration location required")
        handles = []
        try:
            for index, item in enumerate((ROOT, ROOT / "Code", path)):
                directory = index < 2
                handle = self.kernel.CreateFileW(str(item), 0x120089, 1, None, 3, 0x02200000, None)
                if handle == ctypes.c_void_p(-1).value:
                    raise OSError("Protected configuration handle open failed")
                handles.append((handle, directory))
                self._check(
                    handle, directory=directory, owner_sid=owner_sid, guardian_sid=guardian_sid
                )
            size = ctypes.c_longlong()
            handle = handles[-1][0]
            if (
                not self.kernel.GetFileSizeEx(handle, ctypes.byref(size))
                or not 1 <= size.value <= 32768
            ):
                raise ValueError("Bounded configuration file required")
            buffer, count = ctypes.create_string_buffer(size.value), wintypes.DWORD()
            if (
                not self.kernel.ReadFile(handle, buffer, size.value, ctypes.byref(count), None)
                or count.value != size.value
            ):
                raise OSError("Exact configuration read failed")
            for held, directory in handles:
                self._check(
                    held, directory=directory, owner_sid=owner_sid, guardian_sid=guardian_sid
                )
            return buffer.raw
        finally:
            for handle, _ in reversed(handles):
                self.kernel.CloseHandle(handle)


def load_guardian_config(
    path, *, owner_sid, guardian_sid, expected_sha256, expected_manifest_sha256, now
):
    """Trusted deployment supplies all role/hash expectations; no host is created.

    Held handles prevent ordinary write/delete opens during validation. This does
    not protect against administrators, prior writable mappings or full rollback.
    OS file IO still requires an external process deadline.
    """
    if NativePipeIdentity().read_process_identity() != guardian_sid:
        raise PermissionError("Configured guardian process required")
    raw = ProtectedConfigReader().read(path, owner_sid=owner_sid, guardian_sid=guardian_sid)
    config = parse_pinned_host_config(
        raw,
        expected_sha256=expected_sha256,
        expected_manifest_sha256=expected_manifest_sha256,
        now=now,
    )
    if config.owner_sid != owner_sid or config.guardian_sid != guardian_sid:
        raise ValueError("Protected configuration role binding mismatch")
    return config
