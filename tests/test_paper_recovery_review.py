import hashlib
import json
from datetime import UTC, datetime, timedelta

import pytest
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import ec
from fastapi.testclient import TestClient
from fido2.utils import websafe_encode
from fido2.webauthn import AuthenticatorData
from pydantic import ValidationError

from security.paper_owner_passkey import ORIGIN, create_app
from security.paper_recovery_review import RecoveryReview, verify_review_receipt
from tests.test_paper_owner_passkey import enrollment


def setup(tmp_path):
    review_file = tmp_path / "review.json"
    app = TestClient(
        create_app(tmp_path / "owner.json", review_file=review_file),
        base_url=ORIGIN,
        headers={"origin": ORIGIN},
    )
    response, key, credential = enrollment(app.post("/begin/enroll").json()["publicKey"])
    assert app.post("/complete/enroll", json=response).status_code == 200
    now = datetime.now(UTC)
    proposal = RecoveryReview(
        action="APPROVE_READ_ONLY_SERVICE_RECOVERY_PLAN",
        account_binding_sha256="a" * 64,
        failed_journal_sha256="b" * 64,
        enrolled_credential_sha256=hashlib.sha256(bytes(credential)).hexdigest(),
        failed_check_count=1,
        created_at_utc=now,
        expires_at_utc=now + timedelta(hours=1),
    )
    review_file.write_text(proposal.model_dump_json(), encoding="utf-8")
    return app, review_file, proposal, key, credential


def signed_assertion(options, key, credential):
    data = AuthenticatorData.create(hashlib.sha256(b"localhost").digest(), 0x05, 1)
    client_data = json.dumps(
        {"type": "webauthn.get", "challenge": options["challenge"], "origin": ORIGIN}
    ).encode()
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


def test_signed_plan_receipt_verifies_without_authority_and_cannot_be_promoted(tmp_path):
    app, _, proposal, key, credential = setup(tmp_path)
    assert app.get("/recovery-review").json()["digest"] == proposal.digest()
    options = app.post(
        "/begin/review", headers={"X-Owner-Review-Sha256": proposal.digest()}
    ).json()["publicKey"]
    response = signed_assertion(options, key, credential)
    result = app.post("/complete/review", json=response)
    assert result.status_code == 200 and not result.json()["reset_authorized"]
    file = next((tmp_path / "owner-passkey-verifications").glob("*.json"))
    receipt = json.loads(file.read_text(encoding="utf-8"))
    assert verify_review_receipt(
        receipt, credential, expected_review=proposal, current_journal_sha256="b" * 64
    )["recovery_plan_signature_verified"]
    with pytest.raises(ValueError):
        verify_review_receipt(
            receipt, credential, expected_review=proposal, current_journal_sha256="c" * 64
        )
    with pytest.raises(ValueError):
        verify_review_receipt(
            dict(receipt, purpose="AUTHENTICATION_TEST_ONLY"),
            credential,
            expected_review=proposal,
            current_journal_sha256="b" * 64,
        )
    with pytest.raises(ValueError):
        verify_review_receipt(
            dict(receipt, challenge_nonce_hex="00" * 32),
            credential,
            expected_review=proposal,
            current_journal_sha256="b" * 64,
        )
    assert app.post("/complete/review", json=response).status_code == 403


def test_displayed_and_inflight_plan_changes_are_rejected(tmp_path):
    app, file, proposal, key, credential = setup(tmp_path)
    assert app.post("/begin/review").status_code == 409
    options = app.post(
        "/begin/review", headers={"X-Owner-Review-Sha256": proposal.digest()}
    ).json()["publicKey"]
    changed = proposal.model_copy(update={"failed_check_count": 2})
    file.write_text(changed.model_dump_json(), encoding="utf-8")
    assert (
        app.post("/complete/review", json=signed_assertion(options, key, credential)).status_code
        == 403
    )
    assert not (tmp_path / "owner-passkey-verifications").exists()


def test_scope_cannot_enable_resets_trading_or_stale_approval(tmp_path):
    app, file, proposal, _, credential = setup(tmp_path)
    for field in (
        "clear_risk_latches",
        "daily_loss_reset",
        "execution_available",
        "live_authorized",
    ):
        with pytest.raises(ValidationError):
            RecoveryReview.model_validate(dict(proposal.model_dump(), **{field: True}))
    with pytest.raises(ValueError):
        proposal.validate_current(
            credential_sha256=hashlib.sha256(bytes(credential)).hexdigest(),
            now=proposal.expires_at_utc,
        )
    file.unlink()
    assert app.get("/recovery-review").status_code == 409
