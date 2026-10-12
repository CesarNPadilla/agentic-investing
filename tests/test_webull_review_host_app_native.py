"""Engineering-token app/host integration; native IO, synthetic owner signature."""

from concurrent.futures import ThreadPoolExecutor
from queue import Empty, Queue

import pytest
from fastapi.testclient import TestClient

from security.webull_guardian_reference import GuardianReference
from security.webull_guardian_review_host import GuardianReviewHost
from security.webull_owner_review_app import create_app
from security.webull_review_signature import ORIGIN
from security.windows_guardian_exchange_client import GuardianExchangeClient
from security.windows_guardian_exchange_pipe import GuardianExchangePipe
from security.windows_pipe_identity import NativePipeIdentity
from tests.test_webull_owner_review_app import assertion, begin, setup


@pytest.mark.parametrize("fail_second_publication", [False, True])
def test_app_host_native_retention_and_interrupted_confirmation(
    tmp_path, monkeypatch, fail_second_publication
):
    _, journal, credential, envelope, key, envelope_file, _ = setup(tmp_path)
    reference = GuardianReference(tmp_path / "separate-guardian", journal, credential)
    now = envelope.issued_at
    sid = NativePipeIdentity().read_process_identity()
    # Native framing/server-token checks run for real; caller role/clock are
    # injected because this test does not run under the separate guardian account.
    monkeypatch.setattr(
        "security.windows_guardian_request_pipe.dispatch_guardian_connected",
        lambda handle, raw, endpoint, **_: (
            endpoint.handle(raw, now=now) | {"owner_pipe_identity_observed": True}
        ),
    )
    ready = Queue()
    host = GuardianReviewHost(
        reference,
        guardian_sid=sid,
        owner_sid="S-1-5-21-100-200-300-9999",
        provisioned_envelope_sha256=envelope.digest(),
        now=lambda: now,
        pipe_factory=lambda: GuardianExchangePipe(
            guardian_sid=sid, owner_sid="S-1-5-21-100-200-300-9999"
        ),
    )

    def publish(message):
        if fail_second_publication and message["action"] == "CONFIRM_REVIEW_CONSUMPTION":
            raise OSError("Synthetic host publication failure")
        ready.put(message)

    def exchange(raw):
        try:
            message = ready.get(timeout=1)
        except Empty:
            raise TimeoutError("Guardian next phase unavailable") from None
        return GuardianExchangeClient(name=message["pipe_name"], guardian_sid=sid).exchange(raw)

    app = create_app(
        tmp_path / "credential.json",
        envelope_file,
        journal.path,
        now=lambda: now,
        guardian_exchange=exchange,
    )
    with ThreadPoolExecutor(max_workers=1) as pool:
        future = pool.submit(host.run, publish)
        with TestClient(app, base_url=ORIGIN, headers={"origin": ORIGIN}) as client:
            options = begin(client, envelope).json()
            response = client.post("/complete", json=assertion(options, key, credential))
            if fail_second_publication:
                assert response.status_code == 403
                with pytest.raises(OSError):
                    future.result(timeout=6)
                assert not reference.confirmation.exists()
            else:
                assert response.status_code == 200
                assert response.json()["guardian_reference_confirmed"] is True
                assert future.result(timeout=6)["reset_authorized"] is False
                assert reference.confirmation.exists()
            assert journal.verify(credential)["retained_review_count"] == 1
            assert reference.intent.exists() and host.started.exists() and host.terminal.exists()
            assert begin(client, envelope).status_code == 409
