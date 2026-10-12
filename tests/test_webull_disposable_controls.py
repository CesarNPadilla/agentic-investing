import json
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from scripts.webull_disposable_controls_ceremony import ACCOUNT, PLAN, controls_only, digest
from security.webull_guardian_reference import GuardianReference
from security.webull_owner_review_app import create_app
from security.webull_review_journal import ReviewJournal
from security.webull_review_signature import (
    ORIGIN,
    ReviewEnvelope,
    review_challenge,
    verify_review_signature,
)
from tests.test_webull_owner_review_app import assertion
from tests.test_webull_review_signature import signed_review


def fixture():
    _, keydata, legacy, now, key = signed_review()
    value = legacy.model_dump(mode="json")
    value.update(
        schema_version="webull-disposable-controls-review-v1",
        action="REVIEW_DISPOSABLE_CONTROLS_TEST_ONLY",
        account_binding_sha256=digest(ACCOUNT),
        reset_review_sha256=digest(PLAN),
    )
    envelope = ReviewEnvelope.model_validate(value)
    receipt, *_ = signed_review(envelope=envelope, key=key, credential=keydata)
    receipt["purpose"] = "WEBULL_DISPOSABLE_CONTROLS_TEST_ONLY"
    return receipt, keydata, envelope, legacy, now, key


def test_disposable_signature_cannot_become_reset_review():
    receipt, keydata, envelope, legacy, now, _ = fixture()
    assert verify_review_signature(receipt, keydata, expected_envelope=envelope, now=now)
    assert review_challenge(envelope, b"n" * 32) != review_challenge(legacy, b"n" * 32)
    with pytest.raises(ValueError):
        verify_review_signature(receipt, keydata, expected_envelope=legacy, now=now)
    receipt["purpose"] = "WEBULL_RESET_PREREQUISITE_REVIEW_ONLY"
    with pytest.raises(ValueError):
        verify_review_signature(receipt, keydata, expected_envelope=envelope, now=now)


def test_schema_action_and_blueprint_match():
    _, _, envelope, *_ = fixture()
    controls_only(SimpleNamespace(envelope=envelope))
    value = envelope.model_dump(mode="json")
    value["action"] = "REVIEW_WEBULL_RESET_PRECONDITIONS_ONLY"
    with pytest.raises(ValueError):
        ReviewEnvelope.model_validate(value)
    value = envelope.model_dump(mode="json")
    value["account_binding_sha256"] = "a" * 64
    with pytest.raises(ValueError):
        controls_only(SimpleNamespace(envelope=ReviewEnvelope.model_validate(value)))


def test_labeled_controls_page_one_guarded_consumption(tmp_path):
    _, credential, envelope, _, now, key = fixture()
    owner = tmp_path / "owner"
    owner.mkdir()
    journal = ReviewJournal.initialize(owner / "review.sqlite", expected_envelope=envelope)
    directory = tmp_path / "guardian"
    directory.mkdir()
    reference = GuardianReference(directory, journal, credential)
    actions = []

    def exchange(raw):
        actions.append(json.loads(raw)["action"])
        return reference.handle(raw, now=now) | {"owner_pipe_identity_observed": True}

    app = create_app(
        None,
        None,
        None,
        now=lambda: now,
        context_loader=lambda: (envelope, credential, journal),
        guardian_exchange=exchange,
    )
    client = TestClient(app, base_url=ORIGIN, headers={"origin": ORIGIN})
    assert "SYNTHETIC ACCOUNT AND PLAN" in client.get("/").text
    assert "disposable test" in client.get("/").text
    options = client.post("/begin", headers={"x-owner-review-sha256": envelope.digest()}).json()
    result = client.post("/complete", json=assertion(options, key, credential))
    assert result.status_code == 200
    assert result.json()["reset_authorized"] is False
    assert actions == ["PREPARE_REVIEW_REFERENCE", "CONFIRM_REVIEW_CONSUMPTION"]
    assert journal.verify(credential)["retained_review_count"] == 1
    assert client.post("/complete", json={}).status_code == 403
