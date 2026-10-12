"""Staged same-identity Windows process-tree bounds; no service or broker runner."""

import ctypes
import math
import os
import subprocess
import time
from ctypes import wintypes
from pathlib import Path

from workers.windows_child_job import ExtendedLimits, WindowsChildJob


class Startup(ctypes.Structure):
    _fields_ = [
        ("size", wintypes.DWORD),
        ("reserved", wintypes.LPWSTR),
        ("desktop", wintypes.LPWSTR),
        ("title", wintypes.LPWSTR),
        *(
            (name, wintypes.DWORD)
            for name in ("x", "y", "width", "height", "xchars", "ychars", "fill", "flags")
        ),
        ("show", wintypes.WORD),
        ("reserved_size", wintypes.WORD),
        ("reserved2", ctypes.c_void_p),
        ("stdin", wintypes.HANDLE),
        ("stdout", wintypes.HANDLE),
        ("stderr", wintypes.HANDLE),
    ]


class ProcessInfo(ctypes.Structure):
    _fields_ = [
        ("process", wintypes.HANDLE),
        ("thread", wintypes.HANDLE),
        ("pid", wintypes.DWORD),
        ("tid", wintypes.DWORD),
    ]


class Accounting(ctypes.Structure):
    _fields_ = [
        *((name, ctypes.c_int64) for name in ("user", "kernel", "period_user", "period_kernel")),
        *((name, wintypes.DWORD) for name in ("page_faults", "total", "active", "terminated")),
    ]


def supervise_review_process(
    executable, arguments, directory, *, seconds=15, stop_requested=lambda: False
):
    """Only trusted deployment code supplies the executable/arguments.

    Creates a suspended process, attaches it before execution, and supplies a
    replacement environment. Same identity as supervisor; no credential logon.
    Execution permission and protected input qualification are separate gates.
    """
    if type(seconds) not in (int, float) or not math.isfinite(seconds) or not 0 < seconds <= 45:
        raise ValueError("Process deadline must be positive and at most 45 seconds")
    executable, directory = Path(executable), Path(directory)
    if (
        not executable.is_absolute()
        or not executable.is_file()
        or not directory.is_absolute()
        or not directory.is_dir()
    ):
        raise ValueError("Absolute existing executable and working directory required")
    if type(arguments) not in (list, tuple) or any(
        type(arg) is not str or "\0" in arg for arg in arguments
    ):
        raise ValueError("Explicit argument strings required")
    job = WindowsChildJob()
    k = job.api
    declarations = [
        (
            k.CreateProcessW,
            [
                wintypes.LPCWSTR,
                wintypes.LPWSTR,
                ctypes.c_void_p,
                ctypes.c_void_p,
                wintypes.BOOL,
                wintypes.DWORD,
                ctypes.c_void_p,
                wintypes.LPCWSTR,
                ctypes.POINTER(Startup),
                ctypes.POINTER(ProcessInfo),
            ],
            wintypes.BOOL,
        ),
        (k.ResumeThread, [wintypes.HANDLE], wintypes.DWORD),
        (k.WaitForSingleObject, [wintypes.HANDLE, wintypes.DWORD], wintypes.DWORD),
        (k.GetExitCodeProcess, [wintypes.HANDLE, ctypes.POINTER(wintypes.DWORD)], wintypes.BOOL),
        (k.TerminateProcess, [wintypes.HANDLE, wintypes.UINT], wintypes.BOOL),
        (k.TerminateJobObject, [wintypes.HANDLE, wintypes.UINT], wintypes.BOOL),
        (
            k.QueryInformationJobObject,
            [wintypes.HANDLE, ctypes.c_int, ctypes.c_void_p, wintypes.DWORD, ctypes.c_void_p],
            wintypes.BOOL,
        ),
        (k.GetHandleInformation, [wintypes.HANDLE, ctypes.POINTER(wintypes.DWORD)], wintypes.BOOL),
    ]
    for function, args, result in declarations:
        function.argtypes, function.restype = args, result
    child = ProcessInfo()
    assigned = False
    reason = "CHILD_EXITED"
    try:
        limits, flags = ExtendedLimits(), wintypes.DWORD()
        if (
            not k.QueryInformationJobObject(
                job.handle, 9, ctypes.byref(limits), ctypes.sizeof(limits), None
            )
            or limits.basic.flags != 0x2000
        ):
            raise OSError("Kill-on-close job configuration readback failed")
        if not k.GetHandleInformation(job.handle, ctypes.byref(flags)) or flags.value & 1:
            raise OSError("Non-inheritable job handle required")
        env = {
            "SystemRoot": os.environ["SystemRoot"],
            "WINDIR": os.environ["SystemRoot"],
            "PATH": str(Path(os.environ["SystemRoot"]) / "System32"),
            "TEMP": str(directory),
            "TMP": str(directory),
        }
        environment = ctypes.create_unicode_buffer(
            "\0".join(f"{name}={value}" for name, value in sorted(env.items())) + "\0\0"
        )
        command = ctypes.create_unicode_buffer(
            subprocess.list2cmdline([str(executable), *arguments])
        )
        startup = Startup(size=ctypes.sizeof(Startup))
        if not k.CreateProcessW(
            str(executable),
            command,
            None,
            None,
            False,
            0x08000404,
            environment,
            str(directory),
            ctypes.byref(startup),
            ctypes.byref(child),
        ):
            raise OSError("Suspended review process creation failed")
        if not k.AssignProcessToJobObject(job.handle, child.process):
            raise OSError("Suspended review process containment failed")
        assigned = True
        if k.ResumeThread(child.thread) == 0xFFFFFFFF:
            raise OSError("Contained review process resume failed")
        deadline = time.monotonic() + seconds
        while True:
            if stop_requested():
                reason = "STOP_REQUESTED"
                break
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                reason = "DEADLINE_TERMINATED"
                break
            wait = k.WaitForSingleObject(
                child.process, min(100, max(1, math.ceil(remaining * 1000)))
            )
            if wait == 0:
                break
            if wait != 258:
                raise OSError("Review process wait failed")
        if not k.TerminateJobObject(job.handle, 72):
            raise OSError("Review process-tree termination failed")
        cleanup_deadline = time.monotonic() + 5
        while True:
            accounting = Accounting()
            if not k.QueryInformationJobObject(
                job.handle, 1, ctypes.byref(accounting), ctypes.sizeof(accounting), None
            ):
                raise OSError("Review process-tree accounting unavailable")
            if accounting.active == 0:
                break
            if time.monotonic() >= cleanup_deadline:
                raise TimeoutError("Review process-tree cleanup exceeded five seconds")
            time.sleep(0.01)
        code = wintypes.DWORD()
        if not k.GetExitCodeProcess(child.process, ctypes.byref(code)):
            raise OSError("Review process exit result unavailable")
        return {
            "termination": reason,
            "exit_code": code.value,
            "process_tree_active": 0,
            "assigned_before_resume": True,
            "kill_on_parent_close": True,
            "replacement_environment": True,
            "execution_available": False,
            "reset_authorized": False,
            "trial_started": False,
        }
    finally:
        try:
            if child.process and not assigned:
                k.TerminateProcess(child.process, 72)
                k.WaitForSingleObject(child.process, 5000)
            job.close()
        finally:
            if child.thread:
                k.CloseHandle(child.thread)
            if child.process:
                k.CloseHandle(child.process)
