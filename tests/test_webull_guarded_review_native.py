"""Signed synthetic state over native IO; engineering identities, injected caller dispatch."""

import json
from concurrent.futures import ThreadPoolExecutor

import pytest

from security.webull_guarded_review import consume_guarded_review
from security.webull_guardian_recovery_inspection import inspect_guardian_review
from security.windows_guardian_exchange_client import GuardianExchangeClient
from security.windows_guardian_exchange_pipe import GuardianExchangePipe
from security.windows_pipe_identity import NativePipeIdentity
from tests.test_webull_guardian_reference import setup


@pytest.mark.parametrize(
    "lost_ack", [None, "PREPARE_REVIEW_REFERENCE", "CONFIRM_REVIEW_CONSUMPTION"]
)
def test_signed_native_exchange_preserves_ambiguous_state_and_blocks_replay(
    tmp_path, monkeypatch, lost_ack
):
    reference, receipt, credential, now = setup(tmp_path)
    server_sid = NativePipeIdentity().read_process_identity()
    actions = []

    def dispatch(handle, raw, endpoint, **_):
        # Only the cross-account fixture establishes actual owner/guardian roles.
        # This engineering test exercises signatures, persistence and native framing together.
        return endpoint.handle(raw, now=now) | {"owner_pipe_identity_observed": True}

    monkeypatch.setattr(
        "security.windows_guardian_request_pipe.dispatch_guardian_connected", dispatch
    )

    def exchange(raw):
        action = json.loads(raw)["action"]
        actions.append(action)
        pipe = GuardianExchangePipe(guardian_sid=server_sid, owner_sid="S-1-5-21-100-200-300-9999")
        client = GuardianExchangeClient(name=pipe.name, guardian_sid=server_sid)
        with ThreadPoolExecutor(max_workers=1) as pool:
            future = pool.submit(pipe.register_one, reference)
            try:
                response = client.exchange(raw)
                assert future.result(timeout=6) == response
            finally:
                client.close()
        assert pipe.handle is None
        if action == lost_ack:
            raise OSError("Synthetic delivery loss after durable reference write")
        return response

    if lost_ack:
        with pytest.raises(OSError):
            consume_guarded_review(
                receipt, credential, reference.journal, exchange=exchange, now=lambda: now
            )
    else:
        result = consume_guarded_review(
            receipt, credential, reference.journal, exchange=exchange, now=lambda: now
        )
        assert result["guardian_reference_confirmed"] is True
        assert result["reset_authorized"] is False and result["execution_available"] is False
    consumed = lost_ack != "PREPARE_REVIEW_REFERENCE"
    assert reference.intent.exists()
    assert reference.confirmation.exists() is consumed
    assert reference.journal.verify(credential)["retained_review_count"] == int(consumed)
    diagnosis = inspect_guardian_review(reference, now=now)
    assert diagnosis["reference_state"] == (
        "MATCHING_RETAINED_REVIEW_NO_RESET_AUTHORITY"
        if consumed
        else "INTENT_ONLY_RECONCILIATION_REQUIRED"
    )
    assert diagnosis["recovery_authorized"] is False
    # A fresh attempt cannot turn retained/ambiguous evidence into another consumption.
    # An intent-only replay is rejected by the server, which closes without a
    # reply; the native client then reports an IO failure rather than a payload.
    with pytest.raises((ValueError, OSError)):
        consume_guarded_review(
            receipt, credential, reference.journal, exchange=exchange, now=lambda: now
        )
    assert reference.journal.verify(credential)["retained_review_count"] == int(consumed)
