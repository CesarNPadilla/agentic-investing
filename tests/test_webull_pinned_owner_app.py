"""Synthetic HTTP integration; injected identity/readers do not qualify deployment."""

import hashlib
import json
from datetime import timedelta

import pytest
from fastapi.testclient import TestClient

from scripts.webull_signed_host_fixture import synthetic_material
from security import webull_pinned_owner_app as pinned
from security.webull_guardian_reference import GuardianReference
from security.webull_review_journal import ReviewJournal
from security.webull_review_signature import ORIGIN
from tests.test_webull_owner_review_app import assertion
from tests.test_webull_review_signature import signed_review

OWNER, GUARDIAN = "S-1-5-21-1-2-3-1001", "S-1-5-21-1-2-3-1002"


def setup(tmp_path, monkeypatch):
    _, credential, envelope, current, key = signed_review()
    value = synthetic_material(OWNER, GUARDIAN, "a" * 64)["configuration"]
    value.update(
        envelope=envelope.model_dump(mode="json"), public_credential_hex=bytes(credential).hex()
    )
    raw = [json.dumps(value).encode()]
    now = [current]
    identities = []

    def identity(sid):
        assert sid == OWNER
        identities.append(sid)

    monkeypatch.setattr(pinned, "require_standard_owner", identity)

    class Reader:
        def read(self, path, *, owner_sid, guardian_sid):
            assert path == "protected"
            return raw[0]

    monkeypatch.setattr(pinned, "ProtectedConfigReader", Reader)
    journal = ReviewJournal.initialize(tmp_path / "review.sqlite", expected_envelope=envelope)
    monkeypatch.setattr(pinned, "ReviewJournal", lambda *a, **k: journal)
    directory = tmp_path.parent / (tmp_path.name + "-guardian")
    directory.mkdir()
    reference = GuardianReference(directory, journal, credential)
    exchanges = []

    def exchange(request):
        exchanges.append(json.loads(request)["action"])
        return reference.handle(request, now=now[0]) | {"owner_pipe_identity_observed": True}

    args = {
        "owner_sid": OWNER,
        "guardian_sid": GUARDIAN,
        "expected_sha256": hashlib.sha256(raw[0]).hexdigest(),
        "expected_manifest_sha256": "a" * 64,
        "guardian_exchange": exchange,
        "now": lambda: now[0],
    }
    return args, raw, now, identities, exchanges, credential, envelope, key, journal


def test_pinned_http_signature_order_and_replay(tmp_path, monkeypatch):
    args, _, _, identities, actions, credential, envelope, key, journal = setup(
        tmp_path, monkeypatch
    )
    client = TestClient(
        pinned.create_pinned_owner_app("protected", **args),
        base_url=ORIGIN,
        headers={"origin": ORIGIN},
    )
    assert client.get("/review").json()["digest"] == envelope.digest()
    options = client.post("/begin", headers={"x-owner-review-sha256": envelope.digest()}).json()
    response = client.post("/complete", json=assertion(options, key, credential))
    assert response.status_code == 200
    assert actions == ["PREPARE_REVIEW_REFERENCE", "CONFIRM_REVIEW_CONSUMPTION"]
    assert response.json()["reset_authorized"] is False
    assert journal.verify(credential)["retained_review_count"] == 1
    assert (
        client.post("/begin", headers={"x-owner-review-sha256": envelope.digest()}).status_code
        == 409
    )
    assert len(identities) >= 5


@pytest.mark.parametrize("failure", ["identity", "bytes", "expiry"])
def test_request_revalidation_blocks_before_challenge(tmp_path, monkeypatch, failure):
    args, raw, now, _, actions, _, envelope, _, _ = setup(tmp_path, monkeypatch)
    client = TestClient(
        pinned.create_pinned_owner_app("protected", **args),
        base_url=ORIGIN,
        headers={"origin": ORIGIN},
    )
    if failure == "identity":

        def reject(_):
            raise PermissionError("wrong token")

        monkeypatch.setattr(pinned, "require_standard_owner", reject)
    elif failure == "bytes":
        raw[0] += b" "
    else:
        now[0] = envelope.expires_at + timedelta(seconds=1)
    response = client.post("/begin", headers={"x-owner-review-sha256": envelope.digest()})
    assert response.status_code == 409
    assert "set-cookie" not in response.headers
    assert actions == []


@pytest.mark.parametrize("failure", ["identity", "manifest", "role", "missing_exchange"])
def test_startup_rejects_untrusted_context(tmp_path, monkeypatch, failure):
    args, _, _, _, actions, _, _, _, _ = setup(tmp_path, monkeypatch)
    if failure == "identity":

        def reject(_):
            raise PermissionError("wrong token")

        monkeypatch.setattr(pinned, "require_standard_owner", reject)
    elif failure == "manifest":
        args["expected_manifest_sha256"] = "b" * 64
    elif failure == "role":
        args["guardian_sid"] = OWNER
    else:
        args["guardian_exchange"] = None
    with pytest.raises((ValueError, PermissionError, TypeError)):
        pinned.create_pinned_owner_app("protected", **args)
    assert actions == []
