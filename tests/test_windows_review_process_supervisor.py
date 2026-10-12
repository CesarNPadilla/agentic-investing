import subprocess
import sys
from pathlib import Path

import pytest

from security.windows_review_process_supervisor import supervise_review_process


def test_suspended_assignment_and_clean_exit(tmp_path):
    result = supervise_review_process(
        Path(sys.executable), ["-I", "-c", "raise SystemExit(7)"], tmp_path
    )
    assert result["termination"] == "CHILD_EXITED" and result["exit_code"] == 7
    assert result["assigned_before_resume"] and result["process_tree_active"] == 0
    assert not result["execution_available"]


def test_deadline_kills_waiting_child_and_has_no_live_job_processes(tmp_path):
    result = supervise_review_process(
        Path(sys.executable), ["-I", "-c", "import time;time.sleep(60)"], tmp_path, seconds=0.3
    )
    assert result["termination"] == "DEADLINE_TERMINATED"
    assert result["process_tree_active"] == 0


def test_stop_request_kills_child(tmp_path):
    result = supervise_review_process(
        Path(sys.executable),
        ["-I", "-c", "import time;time.sleep(60)"],
        tmp_path,
        stop_requested=lambda: True,
    )
    assert result["termination"] == "STOP_REQUESTED"
    assert result["process_tree_active"] == 0


def test_clean_parent_exit_also_terminates_its_descendant(tmp_path):
    code = "import subprocess,sys;subprocess.Popen([sys.executable,'-I','-c','import time;time.sleep(60)'])"
    result = supervise_review_process(Path(sys.executable), ["-I", "-c", code], tmp_path)
    assert result["termination"] == "CHILD_EXITED"
    assert result["process_tree_active"] == 0


@pytest.mark.parametrize("seconds", [0, 46, float("nan"), True])
def test_invalid_deadline_is_rejected_before_start(tmp_path, seconds):
    with pytest.raises(ValueError):
        supervise_review_process(Path(sys.executable), [], tmp_path, seconds=seconds)


def test_parent_crash_closes_job_and_child_handle_signals(tmp_path):
    import ctypes
    from ctypes import wintypes

    marker = tmp_path / "child.pid"
    child = (
        "import os,time;from pathlib import Path;Path("
        + repr(str(marker))
        + ").write_text(str(os.getpid()));time.sleep(60)"
    )
    root = Path(__file__).resolve().parents[1]
    parent = """import os,sys,time
from pathlib import Path
sys.path.insert(0,sys.argv[1])
from security.windows_review_process_supervisor import supervise_review_process
marker=Path(sys.argv[2])
def crash():
 if marker.exists():
  # Give the external test time to acquire a handle to the live child.
  time.sleep(0.3)
  os._exit(73)
 return False
supervise_review_process(Path(sys.executable),['-I','-c',sys.argv[3]],marker.parent,stop_requested=crash)
"""
    process = subprocess.Popen(
        [sys.executable, "-I", "-c", parent, str(root), str(marker), child],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.PIPE,
    )
    api = ctypes.WinDLL("kernel32", use_last_error=True)
    api.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
    api.OpenProcess.restype = wintypes.HANDLE
    api.WaitForSingleObject.argtypes = [wintypes.HANDLE, wintypes.DWORD]
    api.CloseHandle.argtypes = [wintypes.HANDLE]
    handle = None
    try:
        import time

        deadline = time.monotonic() + 5
        while not marker.exists():
            if time.monotonic() >= deadline:
                pytest.fail("Synthetic child did not start")
            time.sleep(0.01)
        handle = api.OpenProcess(0x100000, False, int(marker.read_text()))
        assert handle
        _, stderr = process.communicate(timeout=5)
        assert process.returncode == 73, stderr.decode()
        assert api.WaitForSingleObject(handle, 5000) == 0
    finally:
        if process.poll() is None:
            process.kill()
            process.wait(timeout=5)
        if handle:
            api.CloseHandle(handle)
