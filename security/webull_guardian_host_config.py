"""Pinned provisioning syntax/material checks; no filesystem trust or activation."""

import hashlib
import json
from datetime import datetime
from pathlib import PureWindowsPath
from typing import Literal

from fido2.webauthn import AttestedCredentialData
from pydantic import UUID4, BaseModel, ConfigDict, Field, model_validator

from security.webull_review_signature import ReviewEnvelope


class GuardianHostConfig(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)
    schema_version: Literal["webull-guardian-host-config-v1"]
    provisioning_id: UUID4
    guardian_sid: str = Field(pattern=r"^S-1-5-21-(?:[0-9]{1,10}-){3}[0-9]{1,10}$")
    owner_sid: str = Field(pattern=r"^S-1-5-21-(?:[0-9]{1,10}-){3}[0-9]{1,10}$")
    installed_manifest_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    envelope: ReviewEnvelope
    public_credential_hex: str = Field(pattern=r"^(?:[0-9a-f]{2}){1,4096}$")
    reference_directory: str
    journal_path: str
    process_deadline_seconds: Literal[15]
    reset_authorized: Literal[False]
    execution_available: Literal[False]
    trial_started: Literal[False]

    @model_validator(mode="before")
    @classmethod
    def exact_scope_types(cls, value):
        if not isinstance(value, dict):
            raise ValueError("Configuration object required")  # noqa: TRY004 - Pydantic validation error
        for field in ("reset_authorized", "execution_available", "trial_started"):
            if type(value.get(field)) is not bool or value[field] is not False:
                raise ValueError("Explicit false scope flags required")
        if type(value.get("process_deadline_seconds")) is not int:
            raise ValueError("Integer process deadline required")
        return value

    @model_validator(mode="after")
    def check_bound_material(self):
        if self.guardian_sid == self.owner_sid:
            raise ValueError("Distinct guardian and owner required")
        for value in (self.guardian_sid, self.owner_sid):
            if any(int(part) > 0xFFFFFFFF for part in value.split("-")[3:]):
                raise ValueError("SID subauthority out of range")
        credential = AttestedCredentialData(bytes.fromhex(self.public_credential_hex))
        if (
            not credential.credential_id
            or hashlib.sha256(bytes(credential)).hexdigest() != self.envelope.credential_sha256
        ):
            raise ValueError("Provisioned public credential mismatch")
        expected_reference = PureWindowsPath(
            r"C:\ProgramData\AgenticInvestingGuardian\References"
        ) / ("Review-" + str(self.provisioning_id))
        expected_journal = (
            PureWindowsPath(r"C:\ProgramData\AgenticInvestingPaper\OwnerControl")
            / ("Review-" + str(self.provisioning_id))
            / "review.sqlite"
        )
        if self.reference_directory != str(expected_reference) or self.journal_path != str(
            expected_journal
        ):
            raise ValueError("Fixed, separate provisioning paths required")
        return self


def parse_pinned_host_config(raw, *, expected_sha256, expected_manifest_sha256, now):
    """Expected hashes must be independently protected, never read from the input.

    Matching bytes are not an ACL/provenance proof. This function creates no host,
    directories, database or approval, and does not read configuration from disk.
    """
    if type(raw) is not bytes or not 1 <= len(raw) <= 32768:
        raise ValueError("Bounded configuration bytes required")
    if hashlib.sha256(raw).hexdigest() != expected_sha256:
        raise ValueError("Pinned configuration digest mismatch")
    if not isinstance(now, datetime) or now.tzinfo is None or now.utcoffset() is None:
        raise ValueError("Aware provisioning clock required")

    def unique(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise ValueError("Duplicate configuration key")
            result[key] = value
        return result

    def reject_constant(_):
        raise ValueError("Nonfinite configuration value")

    value = json.loads(
        raw.decode("utf-8"), object_pairs_hook=unique, parse_constant=reject_constant
    )
    # Validate in JSON mode for UUID/time parsing while retaining strict scalar types.
    config = GuardianHostConfig.model_validate_json(json.dumps(value, allow_nan=False))
    if config.installed_manifest_sha256 != expected_manifest_sha256:
        raise ValueError("Installed release binding mismatch")
    if not config.envelope.issued_at <= now < config.envelope.expires_at:
        raise ValueError("Provisioned review context is not current")
    return config


def validate_configured_reference(config, reference):
    """Check material/path binding only; OS identity/ACLs remain deployment checks."""
    if (
        str(reference.directory) != config.reference_directory
        or str(reference.journal.path) != config.journal_path
    ):
        raise ValueError("Reference path binding mismatch")
    if (
        reference.journal.expected_envelope.digest() != config.envelope.digest()
        or bytes(reference.credential).hex() != config.public_credential_hex
    ):
        raise ValueError("Reference context binding mismatch")
    return {
        "configuration_material_matches": True,
        "filesystem_protection_qualified": False,
        "process_identity_qualified": False,
        "reset_authorized": False,
        "execution_available": False,
        "trial_started": False,
    }
