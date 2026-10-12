"""Strict signed recovery-plan review scope; no reset or journal mutation."""

import hashlib
import json
from datetime import UTC, datetime
from typing import Literal

from fido2.server import Fido2Server
from fido2.utils import websafe_decode
from fido2.webauthn import PublicKeyCredentialRpEntity
from pydantic import BaseModel, ConfigDict, Field, model_validator


class RecoveryReview(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    schema_version: Literal["paper-recovery-review-v1"] = "paper-recovery-review-v1"
    action: Literal["APPROVE_READ_ONLY_SERVICE_RECOVERY_PLAN"]
    account_binding_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    failed_journal_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    enrolled_credential_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    failed_check_count: int = Field(gt=0, strict=True)
    created_at_utc: datetime
    expires_at_utc: datetime
    preserve_failed_journal: Literal[True] = True
    acknowledge_failed_checks_for_read_only_restart: Literal[True] = True
    fresh_reconciliation_required: Literal[True] = True
    mark_failed_checks_successful: Literal[False] = False
    clear_risk_latches: Literal[False] = False
    daily_loss_reset: Literal[False] = False
    execution_available: Literal[False] = False
    trial_started: Literal[False] = False
    live_authorized: Literal[False] = False

    @model_validator(mode="after")
    def bounded(self):
        for instant in (self.created_at_utc, self.expires_at_utc):
            if instant.tzinfo is None or instant.utcoffset() is None:
                raise ValueError("Aware times required")
        if not 0 < (self.expires_at_utc - self.created_at_utc).total_seconds() <= 86400:
            raise ValueError("Review validity must be at most one day")
        return self

    def validate_current(self, *, credential_sha256, now=None):
        now = now or datetime.now(UTC)
        if not self.created_at_utc <= now < self.expires_at_utc:
            raise ValueError("Review expired or future")
        if self.enrolled_credential_sha256 != credential_sha256:
            raise ValueError("Review credential changed")
        return self

    def digest(self):
        encoded = json.dumps(
            self.model_dump(mode="json"), sort_keys=True, separators=(",", ":")
        ).encode()
        return hashlib.sha256(encoded).hexdigest()


def verify_review_receipt(
    receipt, credential, *, expected_review, current_journal_sha256, now=None
):
    """Verify an action-bound plan decision; returns no mutation authority."""
    if (
        receipt.get("purpose") != "RECOVERY_PLAN_REVIEW_ONLY"
        or receipt.get("reset_authorized") is not False
        or receipt.get("execution_available") is not False
    ):
        raise ValueError("Receipt does not cover a recovery plan")
    proposal = RecoveryReview.model_validate(receipt["review"])
    proposal.validate_current(
        credential_sha256=hashlib.sha256(bytes(credential)).hexdigest(), now=now
    )
    if (
        proposal.digest() != expected_review.digest()
        or proposal.digest() != receipt.get("review_sha256")
        or proposal.failed_journal_sha256 != current_journal_sha256
    ):
        raise ValueError("Recovery plan or failed journal changed")
    state = receipt["challenge_state"]
    if state.get("user_verification") != "required":
        raise ValueError("Required user verification missing")
    nonce = bytes.fromhex(receipt["challenge_nonce_hex"])
    if (
        len(nonce) != 32
        or websafe_decode(state["challenge"])
        != hashlib.sha256(nonce + bytes.fromhex(proposal.digest())).digest()
    ):
        raise ValueError("Challenge not bound to recovery plan")
    server = Fido2Server(
        PublicKeyCredentialRpEntity(id="localhost", name="Agentic Investing Owner"),
        verify_origin=lambda origin: origin == "http://localhost:8766",
    )
    server.authenticate_complete(state, [credential], receipt["assertion"])
    return {
        "recovery_plan_signature_verified": True,
        "reset_authorized": False,
        "execution_available": False,
    }
