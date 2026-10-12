import hashlib
import json

import pytest
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import ec
from fastapi.testclient import TestClient
from fido2.utils import websafe_encode
from fido2.webauthn import AuthenticatorData

from security.webull_guardian_reference import GuardianReference
from security.webull_owner_review_app import create_app
from security.webull_review_journal import ReviewJournal
from security.webull_review_signature import ORIGIN
from tests.test_webull_review_signature import signed_review


def setup(tmp_path):
    _, credential, envelope, now, key = signed_review()
    credential_file, envelope_file, journal_file = [
        tmp_path / name for name in ("credential.json", "envelope.json", "review.sqlite")
    ]
    credential_file.write_text(json.dumps({"credential_data": websafe_encode(bytes(credential))}))
    envelope_file.write_text(envelope.model_dump_json())
    journal = ReviewJournal.initialize(journal_file, expected_envelope=envelope)
    reference_directory = tmp_path / "separate-guardian"
    reference_directory.mkdir()
    # Synthetic in-process exchange only: no native identity qualification.
    owner_directory = tmp_path / "owner-state"
    owner_directory.mkdir()
    journal_file.rename(owner_directory / journal_file.name)
    journal_file = owner_directory / journal_file.name
    journal = ReviewJournal(journal_file, expected_envelope=envelope)
    reference = GuardianReference(reference_directory, journal, credential)

    def exchange(raw):
        return reference.handle(raw, now=now) | {"owner_pipe_identity_observed": True}

    tick = [0]
    app = create_app(
        credential_file,
        envelope_file,
        journal_file,
        now=lambda: now,
        clock=lambda: tick[0],
        guardian_exchange=exchange,
    )
    client = TestClient(app, base_url=ORIGIN, headers={"origin": ORIGIN})
    return client, journal, credential, envelope, key, envelope_file, tick


def assertion(options, key, credential):
    client_data = json.dumps(
        {"type": "webauthn.get", "challenge": options["publicKey"]["challenge"], "origin": ORIGIN}
    ).encode()
    data = AuthenticatorData.create(hashlib.sha256(b"localhost").digest(), 0x05, 1)
    signature = key.sign(
        bytes(data) + hashlib.sha256(client_data).digest(), ec.ECDSA(hashes.SHA256())
    )
    return {
        "id": websafe_encode(credential.credential_id),
        "rawId": websafe_encode(credential.credential_id),
        "type": "public-key",
        "response": {
            "clientDataJSON": websafe_encode(client_data),
            "authenticatorData": websafe_encode(bytes(data)),
            "signature": websafe_encode(signature),
            "userHandle": None,
        },
    }


def begin(client, envelope):
    return client.post("/begin", headers={"X-Owner-Review-Sha256": envelope.digest()})


def test_complete_review_is_retained_once_and_never_authorizes_reset(tmp_path):
    client, journal, credential, envelope, key, _, _ = setup(tmp_path)
    assert "does not approve a reset" in client.get("/").text
    assert client.get("/owner.js").status_code == 200
    assert client.get("/review").json()["digest"] == envelope.digest()
    options = begin(client, envelope).json()
    signed = assertion(options, key, credential)
    response = client.post("/complete", json=signed)
    assert response.status_code == 200
    assert response.json()["review_evidence_consumed"]
    assert response.json()["reset_authorized"] is False
    assert response.json()["approval_consumed"] is False
    assert response.json()["guardian_reference_confirmed"] is True
    assert journal.verify(credential)["retained_review_count"] == 1
    assert client.post("/complete", json=signed).status_code == 403
    assert begin(client, envelope).status_code == 409


def test_display_and_inflight_plan_changes_block_signing(tmp_path):
    client, journal, credential, envelope, key, file, _ = setup(tmp_path)
    assert client.post("/begin").status_code == 409
    options = begin(client, envelope).json()
    file.write_text(envelope.model_copy(update={"reset_review_sha256": "c" * 64}).model_dump_json())
    assert client.post("/complete", json=assertion(options, key, credential)).status_code == 403
    assert journal.verify(credential)["retained_review_count"] == 0


def test_bad_signature_consumes_challenge_but_not_review(tmp_path):
    client, journal, credential, envelope, _, _, _ = setup(tmp_path)
    begin(client, envelope)
    assert client.post("/complete", json={"review_signature_verified": True}).status_code == 403
    assert client.post("/complete", json={}).status_code == 403
    assert journal.verify(credential)["retained_review_count"] == 0
    assert begin(client, envelope).status_code == 200


def test_origin_host_controls_and_response_security_headers(tmp_path):
    client, _, _, envelope, _, _, _ = setup(tmp_path)
    assert client.post("/begin", headers={"origin": "https://foreign.example"}).status_code == 403
    assert client.get("/review", headers={"host": "foreign.example"}).status_code == 403
    response = client.get("/review")
    assert response.headers["cache-control"] == "no-store"
    assert response.headers["x-frame-options"] == "DENY"
    assert "frame-ancestors 'none'" in response.headers["content-security-policy"]
    cookie = begin(client, envelope).headers["set-cookie"].lower()
    assert "httponly" in cookie and "samesite=strict" in cookie


def test_expired_and_over_limit_challenges_fail_closed(tmp_path):
    client, journal, credential, envelope, key, _, tick = setup(tmp_path)
    options = begin(client, envelope).json()
    tick[0] = 120
    assert client.post("/complete", json=assertion(options, key, credential)).status_code == 403
    for _ in range(8):
        assert begin(client, envelope).status_code == 200
    assert begin(client, envelope).status_code == 429
    tick[0] = 240
    assert begin(client, envelope).status_code == 200
    assert journal.verify(credential)["retained_review_count"] == 0


def test_oversized_assertion_is_rejected_without_consumption(tmp_path):
    client, journal, credential, envelope, _, _, _ = setup(tmp_path)
    begin(client, envelope)
    assert client.post("/complete", content=b"x" * 65537).status_code == 413
    assert journal.verify(credential)["retained_review_count"] == 0


def test_missing_private_state_and_colliding_paths_are_rejected(tmp_path):
    client, journal, _, envelope, _, _, _ = setup(tmp_path)
    journal.path.unlink()
    assert client.get("/review").status_code == 409
    assert begin(client, envelope).status_code == 409
    assert not journal.path.exists()
    with pytest.raises(ValueError):
        create_app(tmp_path / "same", tmp_path / "same", tmp_path / "other")


def test_app_without_guardian_transport_cannot_issue_challenge(tmp_path):
    app = create_app(tmp_path / "credential", tmp_path / "envelope", tmp_path / "journal")
    client = TestClient(app, base_url=ORIGIN, headers={"origin": ORIGIN})
    response = client.post("/begin")
    assert response.status_code == 503
    assert "set-cookie" not in response.headers
