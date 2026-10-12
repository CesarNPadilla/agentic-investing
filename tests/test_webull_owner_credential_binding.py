import hashlib
import json

import pytest
from fastapi.testclient import TestClient
from fido2.utils import websafe_decode

from security import webull_owner_auth_diagnostic as ceremony
from tests.test_webull_owner_auth_diagnostic import assertion, prepare


def test_binding_signs_exact_candidate_and_no_review_or_reset(tmp_path, monkeypatch):
    client, _, _, credential, key, retained, _, _ = prepare(
        tmp_path, monkeypatch, profile="credential_binding"
    )
    assert "Authorize this displayed public credential" in client.get("/").text
    assert "Bind this credential" in client.get("/").text
    assert client.get("/status").json()["purpose"] == "OWNER_REVIEW_CREDENTIAL_BINDING_ONLY"
    options = client.post("/begin").json()
    response = client.post(
        "/complete", json=assertion(options, credential, key, origin=ceremony.BINDING_ORIGIN)
    )
    assert response.status_code == 200
    result = retained[0]
    assert result["credential_binding_authorized"] is True
    assert result["credential_sha256"] == hashlib.sha256(bytes(credential)).hexdigest()
    assert result["purpose"] == "OWNER_REVIEW_CREDENTIAL_BINDING_ONLY"
    expected = hashlib.sha256(
        ceremony.BINDING_DOMAIN
        + bytes.fromhex(result["nonce_hex"])
        + bytes.fromhex(result["configuration_sha256"])
    ).digest()
    assert websafe_decode(result["challenge_state"]["challenge"]) == expected
    for name in [
        "review_signature_issued",
        "guardian_called",
        "reset_authorized",
        "execution_available",
        "trial_started",
    ]:
        assert result[name] is False
    assert client.post("/complete", json={}).status_code == 403


def test_diagnostic_assertion_origin_cannot_authorize_binding(tmp_path, monkeypatch):
    client, _, _, credential, key, retained, _, _ = prepare(
        tmp_path, monkeypatch, profile="credential_binding"
    )
    options = client.post("/begin").json()
    assert client.post("/complete", json=assertion(options, credential, key)).status_code == 403
    assert retained == []


def test_profiles_have_distinct_challenges_for_same_nonce_and_config(tmp_path, monkeypatch):
    monkeypatch.setattr(ceremony.secrets, "token_bytes", lambda _: b"n" * 32)
    diagnostic, raw, now, credential, *_ = prepare(tmp_path, monkeypatch)
    config = json.loads(raw[0])
    app = ceremony.create_diagnostic_app(
        "protected",
        owner_sid=config["owner_sid"],
        guardian_sid=config["guardian_sid"],
        expected_sha256=hashlib.sha256(raw[0]).hexdigest(),
        expected_manifest_sha256=config["installed_manifest_sha256"],
        retain=lambda _: None,
        now=lambda: now[0],
        profile="credential_binding",
        expected_credential_sha256=hashlib.sha256(bytes(credential)).hexdigest(),
    )
    binding = TestClient(
        app, base_url=ceremony.BINDING_ORIGIN, headers={"origin": ceremony.BINDING_ORIGIN}
    )
    assert (
        diagnostic.post("/begin").json()["publicKey"]["challenge"]
        != binding.post("/begin").json()["publicKey"]["challenge"]
    )


def test_binding_requires_external_candidate_pin_before_context_access():
    with pytest.raises(ValueError, match="Externally pinned"):
        ceremony.create_diagnostic_app(
            "missing",
            owner_sid="owner",
            guardian_sid="guardian",
            expected_sha256="a" * 64,
            expected_manifest_sha256="b" * 64,
            retain=lambda _: None,
            profile="credential_binding",
        )


def test_changed_candidate_blocks_binding_app_startup(tmp_path, monkeypatch):
    _, raw, now, *_ = prepare(tmp_path, monkeypatch)
    config = json.loads(raw[0])
    with pytest.raises(ValueError, match="Binding candidate changed"):
        ceremony.create_diagnostic_app(
            "protected",
            owner_sid=config["owner_sid"],
            guardian_sid=config["guardian_sid"],
            expected_sha256=hashlib.sha256(raw[0]).hexdigest(),
            expected_manifest_sha256=config["installed_manifest_sha256"],
            retain=lambda _: None,
            now=lambda: now[0],
            profile="credential_binding",
            expected_credential_sha256="0" * 64,
        )
