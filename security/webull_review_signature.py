"""Action-bound WebAuthn review verification, without reset or trading authority."""

import hashlib
import json
from datetime import datetime
from typing import Literal

from fido2.server import Fido2Server
from fido2.utils import websafe_decode
from fido2.webauthn import PublicKeyCredentialRpEntity
from pydantic import UUID4, AwareDatetime, BaseModel, ConfigDict, Field, model_validator

ORIGIN = "http://localhost:8767"
DOMAIN = b"WEBULL_RESET_PREREQUISITE_REVIEW_V1\0"
CONTROLS_DOMAIN = b"WEBULL_DISPOSABLE_CONTROLS_REVIEW_V1\0"


class ReviewEnvelope(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    schema_version: Literal[
        "webull-reset-prerequisite-review-v1", "webull-disposable-controls-review-v1"
    ]
    action: Literal[
        "REVIEW_WEBULL_RESET_PRECONDITIONS_ONLY", "REVIEW_DISPOSABLE_CONTROLS_TEST_ONLY"
    ]
    review_id: UUID4
    account_binding_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    reset_review_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    credential_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    issued_at: AwareDatetime
    expires_at: AwareDatetime

    @model_validator(mode="after")
    def bounded_window(self):
        if (self.schema_version == "webull-disposable-controls-review-v1") != (
            self.action == "REVIEW_DISPOSABLE_CONTROLS_TEST_ONLY"
        ):
            raise ValueError("Review schema and action must match")
        if not 0 < (self.expires_at - self.issued_at).total_seconds() <= 300:
            raise ValueError("Review window must be positive and at most five minutes")
        return self

    def digest(self):
        return hashlib.sha256(
            json.dumps(self.model_dump(mode="json"), sort_keys=True, separators=(",", ":")).encode()
        ).hexdigest()


def review_purpose(envelope: ReviewEnvelope):
    return (
        "WEBULL_DISPOSABLE_CONTROLS_TEST_ONLY"
        if envelope.action == "REVIEW_DISPOSABLE_CONTROLS_TEST_ONLY"
        else "WEBULL_RESET_PREREQUISITE_REVIEW_ONLY"
    )


def review_challenge(envelope: ReviewEnvelope, nonce: bytes):
    if type(nonce) is not bytes or len(nonce) != 32:
        raise ValueError("32-byte server nonce required")
    domain = (
        CONTROLS_DOMAIN if envelope.action == "REVIEW_DISPOSABLE_CONTROLS_TEST_ONLY" else DOMAIN
    )
    return hashlib.sha256(domain + nonce + bytes.fromhex(envelope.digest())).digest()


def verify_review_signature(
    receipt, credential, *, expected_envelope: ReviewEnvelope, now: datetime
):
    """Expected envelope and credential must come from protected controller state.

    This verifies a review signature only. It does not consume a nonce, establish
    OS isolation, approve a reset or convert synthetic prerequisites into proof.
    """
    if now.tzinfo is None or now.utcoffset() is None:
        raise ValueError("Aware verifier clock required")
    try:
        if set(receipt) != {
            "purpose",
            "envelope",
            "envelope_sha256",
            "challenge_nonce_hex",
            "challenge_state",
            "assertion",
            "reset_authorized",
            "execution_available",
        } or (
            receipt["purpose"] != review_purpose(expected_envelope)
            or receipt["reset_authorized"] is not False
            or receipt["execution_available"] is not False
        ):
            raise ValueError("Wrong review scope")
        envelope = ReviewEnvelope.model_validate(receipt["envelope"])
        if (
            envelope.digest() != expected_envelope.digest()
            or envelope.digest() != receipt["envelope_sha256"]
            or envelope.credential_sha256 != hashlib.sha256(bytes(credential)).hexdigest()
            or not envelope.issued_at <= now < envelope.expires_at
        ):
            raise ValueError("Changed, expired or foreign review")
        state = receipt["challenge_state"]
        nonce = bytes.fromhex(receipt["challenge_nonce_hex"])
        if state.get("user_verification") != "required" or websafe_decode(
            state["challenge"]
        ) != review_challenge(envelope, nonce):
            raise ValueError("Unbound challenge or missing user verification")
        server = Fido2Server(
            PublicKeyCredentialRpEntity(id="localhost", name="Agentic Investing Webull Owner"),
            verify_origin=lambda value: value == ORIGIN,
        )
        server.authenticate_complete(state, [credential], receipt["assertion"])
    except (ValueError, TypeError, KeyError, AttributeError):
        raise ValueError("Webull review signature rejected") from None
    return {
        "review_signature_verified": True,
        "review_id": str(envelope.review_id),
        "envelope_sha256": envelope.digest(),
        "approval_consumed": False,
        "reset_authorized": False,
        "execution_available": False,
        "trial_started": False,
    }
