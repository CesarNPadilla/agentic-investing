import hashlib
import json

from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import ec
from fastapi.testclient import TestClient
from fido2 import cbor
from fido2.cose import ES256
from fido2.utils import websafe_encode
from fido2.webauthn import AttestedCredentialData, AuthenticatorData

from security.paper_owner_passkey import ORIGIN, create_app


def client(tmp_path, **kwargs):
    return TestClient(
        create_app(tmp_path / "owner.json", **kwargs), base_url=ORIGIN, headers={"origin": ORIGIN}
    )


def enrollment(options, *, verified=True, origin=ORIGIN):
    key = ec.generate_private_key(ec.SECP256R1())
    credential = AttestedCredentialData.create(
        b"\0" * 16, b"fixture-credential", ES256.from_cryptography_key(key.public_key())
    )
    data = AuthenticatorData.create(
        hashlib.sha256(b"localhost").digest(), 0x45 if verified else 0x41, 0, credential
    )
    client_data = json.dumps(
        {"type": "webauthn.create", "challenge": options["challenge"], "origin": origin}
    ).encode()
    response = {
        "id": websafe_encode(credential.credential_id),
        "rawId": websafe_encode(credential.credential_id),
        "type": "public-key",
        "response": {
            "clientDataJSON": websafe_encode(client_data),
            "attestationObject": websafe_encode(
                cbor.encode({"fmt": "none", "authData": bytes(data), "attStmt": {}})
            ),
        },
    }
    return response, key, credential


def test_real_verifier_accepts_signed_fixture_and_never_grants_reset(tmp_path):
    app = client(tmp_path)
    options = app.post("/begin/enroll").json()["publicKey"]
    assert options["authenticatorSelection"]["userVerification"] == "required"
    response, key, credential = enrollment(options)
    enrolled = app.post("/complete/enroll", json=response)
    assert enrolled.status_code == 200 and not enrolled.json()["reset_authorized"]
    assert app.post("/begin/enroll").status_code == 409
    options = app.post("/begin/verify").json()["publicKey"]
    data = AuthenticatorData.create(hashlib.sha256(b"localhost").digest(), 0x05, 1)
    client_data = json.dumps(
        {"type": "webauthn.get", "challenge": options["challenge"], "origin": ORIGIN}
    ).encode()
    signature = key.sign(
        bytes(data) + hashlib.sha256(client_data).digest(), ec.ECDSA(hashes.SHA256())
    )
    assertion = {
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
    result = app.post("/complete/verify", json=assertion)
    assert result.status_code == 200 and not result.json()["execution_available"]
    audit = list((tmp_path / "owner-passkey-verifications").glob("*.json"))
    assert len(audit) == 1
    row = json.loads(audit[0].read_text(encoding="utf-8"))
    assert row["purpose"] == "AUTHENTICATION_TEST_ONLY" and not row["reset_authorized"]
    assert app.post("/complete/verify", json=assertion).status_code == 403
    assert len(list((tmp_path / "owner-passkey-verifications").glob("*.json"))) == 1
    assert app.post("/reset").status_code == 404


def test_origin_uv_expiry_and_replay_rejected(tmp_path):
    ticks = [0]
    app = client(tmp_path, clock=lambda: ticks[0])
    assert app.post("/begin/enroll", headers={"origin": "https://evil.example"}).status_code == 403
    assert app.get("/", headers={"host": "evil.example"}).status_code == 403
    options = app.post("/begin/enroll").json()["publicKey"]
    response, _, _ = enrollment(options, verified=False)
    assert app.post("/complete/enroll", json=response).status_code == 403
    assert not (tmp_path / "owner.json").exists()
    options = app.post("/begin/enroll").json()["publicKey"]
    response, _, _ = enrollment(options, origin="https://evil.example")
    assert app.post("/complete/enroll", json=response).status_code == 403
    options = app.post("/begin/enroll").json()["publicKey"]
    response, _, _ = enrollment(options)
    ticks[0] = 121
    assert app.post("/complete/enroll", json=response).status_code == 403
    assert not (tmp_path / "owner.json").exists()
