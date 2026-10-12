import copy
import hashlib
import json
from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import ec
from fido2.cose import ES256
from fido2.utils import websafe_encode
from fido2.webauthn import AttestedCredentialData, AuthenticatorData
from pydantic import ValidationError

from security.webull_review_signature import (
    ORIGIN,
    ReviewEnvelope,
    review_challenge,
    verify_review_signature,
)


def signed_review(*, origin=ORIGIN, flags=0x05, envelope=None, key=None, credential=None):
    key = key or ec.generate_private_key(ec.SECP256R1())
    credential = credential or AttestedCredentialData.create(
        b"\0" * 16, b"fixture-credential", ES256.from_cryptography_key(key.public_key())
    )
    now = datetime(2026, 10, 8, 16, tzinfo=UTC)
    envelope = envelope or ReviewEnvelope(
        schema_version="webull-reset-prerequisite-review-v1",
        action="REVIEW_WEBULL_RESET_PRECONDITIONS_ONLY",
        review_id=uuid4(),
        account_binding_sha256="a" * 64,
        reset_review_sha256="b" * 64,
        credential_sha256=hashlib.sha256(bytes(credential)).hexdigest(),
        issued_at=now,
        expires_at=now + timedelta(seconds=300),
    )
    nonce = b"n" * 32
    challenge = websafe_encode(review_challenge(envelope, nonce))
    client_data = json.dumps(
        {"type": "webauthn.get", "challenge": challenge, "origin": origin}
    ).encode()
    data = AuthenticatorData.create(hashlib.sha256(b"localhost").digest(), flags, 1)
    signature = key.sign(
        bytes(data) + hashlib.sha256(client_data).digest(), ec.ECDSA(hashes.SHA256())
    )
    receipt = {
        "purpose": "WEBULL_RESET_PREREQUISITE_REVIEW_ONLY",
        "envelope": envelope.model_dump(mode="json"),
        "envelope_sha256": envelope.digest(),
        "challenge_nonce_hex": nonce.hex(),
        "challenge_state": {"challenge": challenge, "user_verification": "required"},
        "assertion": {
            "id": websafe_encode(credential.credential_id),
            "rawId": websafe_encode(credential.credential_id),
            "type": "public-key",
            "response": {
                "clientDataJSON": websafe_encode(client_data),
                "authenticatorData": websafe_encode(bytes(data)),
                "signature": websafe_encode(signature),
                "userHandle": None,
            },
        },
        "reset_authorized": False,
        "execution_available": False,
    }
    return receipt, credential, envelope, now, key


def test_actual_crypto_fixture_verifies_only_review_scope():
    receipt, credential, envelope, now, _ = signed_review()
    result = verify_review_signature(receipt, credential, expected_envelope=envelope, now=now)
    assert result["review_signature_verified"]
    for name in ("approval_consumed", "reset_authorized", "execution_available", "trial_started"):
        assert result[name] is False


@pytest.mark.parametrize("origin,flags", [("http://localhost:8766", 5), (ORIGIN, 1), (ORIGIN, 4)])
def test_foreign_origin_and_missing_presence_or_verification_rejected(origin, flags):
    receipt, credential, envelope, now, _ = signed_review(origin=origin, flags=flags)
    with pytest.raises(ValueError):
        verify_review_signature(receipt, credential, expected_envelope=envelope, now=now)


@pytest.mark.parametrize(
    "field,value",
    [
        ("purpose", "AUTHENTICATION_TEST_ONLY"),
        ("reset_authorized", True),
        ("execution_available", True),
        ("envelope_sha256", "c" * 64),
        ("challenge_nonce_hex", "00" * 32),
        ("unexpected", False),
    ],
)
def test_modified_receipt_rejected(field, value):
    receipt, credential, envelope, now, _ = signed_review()
    receipt[field] = value
    with pytest.raises(ValueError):
        verify_review_signature(receipt, credential, expected_envelope=envelope, now=now)


@pytest.mark.parametrize("seconds", [-1, 300, 301])
def test_signature_is_not_fresh_outside_half_open_window(seconds):
    receipt, credential, envelope, now, _ = signed_review()
    with pytest.raises(ValueError):
        verify_review_signature(
            receipt, credential, expected_envelope=envelope, now=now + timedelta(seconds=seconds)
        )


def test_wrong_credential_changed_plan_or_signature_and_optional_uv_rejected():
    receipt, credential, envelope, now, _ = signed_review()
    _, foreign, _, _, _ = signed_review()
    for changed, cred, expected in [
        (receipt, foreign, envelope),
        (receipt, credential, envelope.model_copy(update={"reset_review_sha256": "c" * 64})),
    ]:
        with pytest.raises(ValueError):
            verify_review_signature(changed, cred, expected_envelope=expected, now=now)
    for mutate in ("signature", "state", "envelope"):
        changed = copy.deepcopy(receipt)
        if mutate == "signature":
            changed["assertion"]["response"]["signature"] = websafe_encode(b"invalid")
        elif mutate == "state":
            changed["challenge_state"]["user_verification"] = "preferred"
        else:
            changed["envelope"]["account_binding_sha256"] = "c" * 64
            changed["envelope_sha256"] = ReviewEnvelope.model_validate(changed["envelope"]).digest()
        with pytest.raises(ValueError):
            verify_review_signature(changed, credential, expected_envelope=envelope, now=now)


@pytest.mark.parametrize("seconds", [0, -1, 301])
def test_invalid_envelope_lifetime_rejected(seconds):
    _, _, envelope, now, _ = signed_review()
    value = envelope.model_dump()
    value["expires_at"] = now + timedelta(seconds=seconds)
    with pytest.raises(ValidationError):
        ReviewEnvelope.model_validate(value)


def test_invalid_nonce_rejected():
    _, _, envelope, _, _ = signed_review()
    for nonce in (b"", b"x" * 31, "x" * 32):
        with pytest.raises(ValueError):
            review_challenge(envelope, nonce)
