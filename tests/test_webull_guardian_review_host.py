import json
from unittest.mock import Mock

import pytest

from security.webull_guardian_review_host import GuardianReviewHost
from tests.test_webull_guardian_reference import request, setup


def host_for(reference, now, factory):
    return GuardianReviewHost(
        reference,
        guardian_sid="S-1-5-21-100",
        owner_sid="S-1-5-21-200",
        provisioned_envelope_sha256=reference.journal.expected_envelope.digest(),
        now=lambda: now,
        pipe_factory=factory,
    )


def test_host_orders_requests_closes_pipes_and_cannot_restart(tmp_path):
    reference, receipt, credential, now = setup(tmp_path)
    pipes = []

    def factory():
        pipe = Mock(name="pipe")
        pipe.name = "synthetic-pipe"
        action = "PREPARE_REVIEW_REFERENCE" if not pipes else "CONFIRM_REVIEW_CONSUMPTION"

        def register(endpoint, **_):
            result = endpoint.handle(
                request(reference, receipt if len(pipes) == 1 else None, action=action), now=now
            )
            if action == "PREPARE_REVIEW_REFERENCE":
                reference.journal.consume(receipt, credential, now=now)
            return result

        pipe.register_one.side_effect = register
        pipes.append(pipe)
        return pipe

    host = host_for(reference, now, factory)
    ready = []
    result = host.run(ready.append)
    assert result["state"] == "REVIEW_RETAINED_HOST_CLOSED_NO_RESET_AUTHORITY"
    assert len(ready) == 2 and all(pipe.close.call_count == 1 for pipe in pipes)
    assert result["reset_authorized"] is False and result["execution_available"] is False
    with pytest.raises(ValueError):
        host.run(ready.append)
    with pytest.raises(ValueError):
        host_for(reference, now, factory).run(ready.append)


@pytest.mark.parametrize("fault", ["publish", "transport", "order", "stop"])
def test_failure_closes_and_leaves_start_and_blocked_terminal(tmp_path, fault):
    reference, _receipt, _, now = setup(tmp_path)
    pipe = Mock()
    pipe.name = "synthetic-pipe"
    if fault == "order":
        pipe.register_one.side_effect = lambda endpoint, **_: endpoint.handle(
            request(reference, action="CONFIRM_REVIEW_CONSUMPTION"), now=now
        )
    else:
        pipe.register_one.side_effect = TimeoutError("Synthetic timeout")
    publish = Mock(
        side_effect=OSError("Synthetic publication failure") if fault == "publish" else None
    )
    host = host_for(reference, now, lambda: pipe)
    with pytest.raises((OSError, ValueError)):
        host.run(publish, stop_requested=lambda: fault == "stop")
    assert host.started.exists()
    assert json.loads(host.terminal.read_text())["state"] == "BLOCKED_RECONCILIATION_REQUIRED"
    if fault != "stop":
        pipe.close.assert_called_once()
    assert not reference.intent.exists()
    with pytest.raises((ValueError, FileExistsError)):
        host_for(reference, now, lambda: pipe).run(publish)


def test_crash_start_marker_alone_blocks_new_host(tmp_path):
    reference, _, _, now = setup(tmp_path)
    host = host_for(reference, now, Mock())
    host.started.write_text("retained interrupted start")
    with pytest.raises(FileExistsError):
        host.run(Mock())
    assert not host.terminal.exists()


def test_provisioned_context_digest_must_match(tmp_path):
    reference, _, _, _now = setup(tmp_path)
    with pytest.raises(ValueError):
        GuardianReviewHost(
            reference,
            guardian_sid="S-1-5-21-100",
            owner_sid="S-1-5-21-200",
            provisioned_envelope_sha256="0" * 64,
        )
