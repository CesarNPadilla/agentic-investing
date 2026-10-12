import hashlib
import json

import pytest
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import ec
from fastapi.testclient import TestClient
from fido2.utils import websafe_encode
from fido2.webauthn import AuthenticatorData

from security import webull_owner_auth_diagnostic as diagnostic
from security import webull_pinned_owner_app as pinned
from tests.test_webull_pinned_owner_app import setup


def prepare(tmp_path, monkeypatch, *, profile="diagnostic"):
    args, raw, now, _, _, credential, _, key, journal = setup(tmp_path, monkeypatch)
    monkeypatch.setattr(diagnostic, "require_standard_owner", pinned.require_standard_owner)
    monkeypatch.setattr(diagnostic, "ProtectedConfigReader", pinned.ProtectedConfigReader)
    args.pop("guardian_exchange")
    retained, tick = [], [0]
    app = diagnostic.create_diagnostic_app(
        "protected",
        **args,
        retain=retained.append,
        clock=lambda: tick[0],
        profile=profile,
        expected_credential_sha256=hashlib.sha256(bytes(credential)).hexdigest(),
    )
    origin = diagnostic.BINDING_ORIGIN if profile == "credential_binding" else diagnostic.ORIGIN
    client = TestClient(app, base_url=origin, headers={"origin": origin})
    return client, raw, now, credential, key, retained, tick, journal


def assertion(options, credential, key, *, origin=diagnostic.ORIGIN, flags=5):
    data = json.dumps(
        {"type": "webauthn.get", "challenge": options["publicKey"]["challenge"], "origin": origin}
    ).encode()
    auth = AuthenticatorData.create(hashlib.sha256(b"localhost").digest(), flags, 1)
    signature = key.sign(bytes(auth) + hashlib.sha256(data).digest(), ec.ECDSA(hashes.SHA256()))
    return {
        "id": websafe_encode(credential.credential_id),
        "rawId": websafe_encode(credential.credential_id),
        "type": "public-key",
        "response": {
            "clientDataJSON": websafe_encode(data),
            "authenticatorData": websafe_encode(bytes(auth)),
            "signature": websafe_encode(signature),
            "userHandle": None,
        },
    }


def test_authentication_retains_diagnostic_only_and_blocks_replay(tmp_path, monkeypatch):
    client, _, _, credential, key, retained, _, journal = prepare(tmp_path, monkeypatch)
    before = journal.path.read_bytes()
    assert client.get("/status").json()["purpose"] == "OWNER_AUTH_DIAGNOSTIC_ONLY"
    assert "does not approve" in client.get("/").text
    assert client.get("/owner.js").status_code == 200
    options = client.post("/begin").json()
    response = client.post("/complete", json=assertion(options, credential, key))
    assert response.status_code == 200
    assert len(retained) == 1
    for flag in [
        "review_signature_issued",
        "guardian_called",
        "reset_authorized",
        "execution_available",
        "trial_started",
    ]:
        assert retained[0][flag] is False
    assert journal.path.read_bytes() == before
    assert client.post("/complete", json={}).status_code == 403
    assert client.post("/begin").status_code == 409


@pytest.mark.parametrize("failure", ["origin", "verification", "expiry", "configuration"])
def test_failed_authentication_is_never_retained(tmp_path, monkeypatch, failure):
    client, raw, _, credential, key, retained, tick, _ = prepare(tmp_path, monkeypatch)
    options = client.post("/begin").json()
    kwargs = {}
    if failure == "origin":
        kwargs["origin"] = "http://localhost:8767"
    elif failure == "verification":
        kwargs["flags"] = 1
    elif failure == "expiry":
        tick[0] = 31
    else:
        raw[0] += b" "
    assert (
        client.post("/complete", json=assertion(options, credential, key, **kwargs)).status_code
        == 403
    )
    assert retained == []


def test_nonlocal_origin_and_duplicate_challenges_rejected(tmp_path, monkeypatch):
    client, *_ = prepare(tmp_path, monkeypatch)
    assert client.post("/begin", headers={"origin": "http://example.com"}).status_code == 403
    assert client.post("/begin").status_code == 200
    assert client.post("/begin").status_code == 409
