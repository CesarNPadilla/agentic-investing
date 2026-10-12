import json
import subprocess
from pathlib import Path

import pytest

from workers.webull_event_probe import supervise_probe


def run_fake(tmp_path, *, attach_error=False, promoted=False):
    root = tmp_path / "repo"
    private = tmp_path / "private"
    private.mkdir()
    calls = []

    class Process:
        pid = 123
        returncode = None

        def wait(self, timeout):
            calls.append(("wait", timeout))
            if self.returncode is None:
                raise subprocess.TimeoutExpired("diagnostic", timeout)
            return self.returncode

        def poll(self):
            return self.returncode

        def kill(self):
            self.returncode = -1
            calls.append("kill")

    process = Process()

    class Job:
        def attach(self, child):
            calls.append("attach")
            if attach_error:
                raise OSError("fixture attach failed")

        def close(self):
            calls.append("close")
            process.returncode = -1

    def factory(command, **kwargs):
        assert kwargs["stdout"] == kwargs["stderr"] == subprocess.DEVNULL
        assert kwargs["stdin"] == subprocess.DEVNULL
        gate = Path(command[command.index("--startup-gate") + 1])
        assert not gate.exists()
        report = Path(command[command.index("--child-report") + 1])
        report.write_text(
            json.dumps(
                {
                    "schema_version": "webull-event-observation-v1",
                    "execution_available": promoted,
                    "trial_started": False,
                    "subscribed": True,
                    "heartbeat_count": 0,
                }
            )
        )
        return process

    result = supervise_probe(
        root,
        private / "sandbox.env",
        private / "selection.json",
        seconds=2,
        process_factory=factory,
        job_factory=Job,
    )
    assert not list(private.glob("*.gate"))
    return result, calls


def test_deadline_containment_does_not_promote_quiet_subscription(tmp_path):
    result, calls = run_fake(tmp_path)
    assert result["termination"] == "DEADLINE_TERMINATED"
    assert result["child_contained"] and result["child_exit_code"] == -1
    assert not result["missed_event_coverage"]
    assert not result["continuous_supervision_qualified"]
    assert calls == ["attach", ("wait", 2), "close", ("wait", 5)]


def test_attachment_failure_prevents_startup_handshake(tmp_path):
    with pytest.raises(OSError, match="attach failed"):
        run_fake(tmp_path, attach_error=True)
    assert not list(tmp_path.rglob("*.gate"))


def test_child_cannot_promote_execution(tmp_path):
    with pytest.raises(ValueError, match="evidence invalid"):
        run_fake(tmp_path, promoted=True)
    assert not list(tmp_path.rglob("*.gate"))


@pytest.mark.parametrize("seconds", [0, 46, True])
def test_invalid_deadline_rejected_before_launch(tmp_path, seconds):
    with pytest.raises(ValueError):
        supervise_probe(
            tmp_path / "repo", tmp_path / "env", tmp_path / "selection", seconds=seconds
        )


def test_repository_credentials_rejected_before_launch(tmp_path):
    with pytest.raises(ValueError, match="outside repository"):
        supervise_probe(tmp_path, tmp_path / "env", tmp_path / "selection")
