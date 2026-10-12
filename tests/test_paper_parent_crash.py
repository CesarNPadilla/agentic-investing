import ctypes
import subprocess
import sys
import time
from ctypes import wintypes

import pytest

from tests.test_paper_event_process_supervisor import child_factory, run, setup
from workers.paper_startup_gate import await_startup_gate


def test_actual_parent_death_terminates_contained_child(tmp_path):
    marker = tmp_path / "child-ready.txt"
    code = """
import subprocess,sys,time
from pathlib import Path
from workers.windows_child_job import WindowsChildJob
job=WindowsChildJob()
child=subprocess.Popen([sys.executable,'-c','import time;time.sleep(30)'],
    stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,creationflags=subprocess.CREATE_NO_WINDOW)
job.attach(child)
marker=Path(sys.argv[1])
temporary=marker.with_suffix('.tmp')
temporary.write_text(str(child.pid),encoding='ascii')
temporary.replace(marker)
time.sleep(30)
"""
    parent = subprocess.Popen(
        [sys.executable, "-c", code, str(marker)],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        creationflags=subprocess.CREATE_NO_WINDOW,
    )
    handle = None
    api = ctypes.WinDLL("kernel32", use_last_error=True)
    api.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
    api.OpenProcess.restype = wintypes.HANDLE
    api.WaitForSingleObject.argtypes = [wintypes.HANDLE, wintypes.DWORD]
    api.WaitForSingleObject.restype = wintypes.DWORD
    api.CloseHandle.argtypes = [wintypes.HANDLE]
    try:
        deadline = time.monotonic() + 5
        while not marker.exists() and time.monotonic() < deadline and parent.poll() is None:
            time.sleep(0.02)
        assert marker.exists(), "Contained child must become ready"
        handle = api.OpenProcess(0x00100000, False, int(marker.read_text(encoding="ascii")))
        assert handle
        parent.kill()
        parent.wait(timeout=2)
        assert api.WaitForSingleObject(handle, 5000) == 0
    finally:
        if parent.poll() is None:
            parent.kill()
            parent.wait(timeout=2)
        if handle:
            api.CloseHandle(handle)


def test_startup_gate_requires_matching_parent_release_and_is_bounded(tmp_path):
    root = tmp_path / "repo"
    root.mkdir()
    gate = tmp_path / "private-gate"
    with pytest.raises(TimeoutError):
        await_startup_gate(gate, "expected", root=root, timeout=0.05)
    gate.write_text("wrong", encoding="ascii")
    with pytest.raises(ValueError):
        await_startup_gate(gate, "expected", root=root)
    gate.write_text("expected", encoding="ascii")
    await_startup_gate(gate, "expected", root=root)
    with pytest.raises(ValueError):
        await_startup_gate(root / "gate", "expected", root=root)


def test_assignment_failure_never_releases_gate_or_admits_child(tmp_path):
    root, store = setup(tmp_path)
    children = []

    class FailedJob:
        def attach(self, process):
            raise OSError("Assignment failed")

        def close(self):
            pass

    result = run(
        root, store, child_factory("import time;time.sleep(30)", children), job_factory=FailedJob
    )
    assert not result["monitor_completed"] and result["child_terminated"]
    assert children[0].poll() is not None
    assert not list(tmp_path.glob("paper-child-gate-*"))
