"""Verify explicit credential adoption evidence; no review or execution authority."""

import hashlib
import json
from datetime import datetime

from fido2.server import Fido2Server
from fido2.utils import websafe_decode
from fido2.webauthn import AttestedCredentialData, PublicKeyCredentialRpEntity

from security.webull_guardian_host_config import parse_pinned_host_config

BINDING_ORIGIN = "http://localhost:8769"
BINDING_DOMAIN = b"WEBULL_OWNER_REVIEW_CREDENTIAL_BINDING_ONLY_V1\0"


def verify_binding(
    result,
    configuration,
    *,
    configuration_sha256,
    manifest_sha256,
    credential_sha256,
    owner_sid,
    guardian_sid,
):
    """External deployment pins are mandatory; receipt booleans alone prove nothing."""
    if (
        result.get("schema_version") != "owner-credential-binding-v1"
        or result.get("purpose") != "OWNER_REVIEW_CREDENTIAL_BINDING_ONLY"
    ):
        raise ValueError("Explicit credential binding required")
    for name in (
        "authentication_verified",
        "credential_binding_authorized",
        "standard_owner_process_verified",
    ):
        if result.get(name) is not True:
            raise ValueError("Binding verification required")
    for name in (
        "review_signature_issued",
        "guardian_called",
        "reset_authorized",
        "execution_available",
        "trial_started",
    ):
        if result.get(name) is not False:
            raise ValueError("Binding-only scope required")
    observed = datetime.fromisoformat(result["observed_at_utc"])
    config = parse_pinned_host_config(
        configuration,
        expected_sha256=configuration_sha256,
        expected_manifest_sha256=manifest_sha256,
        now=observed,
    )
    if config.owner_sid != owner_sid or config.guardian_sid != guardian_sid:
        raise ValueError("Independent Windows role binding required")
    credential = AttestedCredentialData(bytes.fromhex(config.public_credential_hex))
    if (
        hashlib.sha256(bytes(credential)).hexdigest() != credential_sha256
        or result.get("credential_sha256") != credential_sha256
        or result.get("configuration_sha256") != configuration_sha256
    ):
        raise ValueError("Independent credential/configuration binding required")
    nonce = bytes.fromhex(result["nonce_hex"])
    state = result["challenge_state"]
    if (
        len(nonce) != 32
        or state.get("user_verification") != "required"
        or websafe_decode(state["challenge"])
        != hashlib.sha256(BINDING_DOMAIN + nonce + bytes.fromhex(configuration_sha256)).digest()
    ):
        raise ValueError("Binding challenge domain and required verification mismatch")
    Fido2Server(
        PublicKeyCredentialRpEntity(id="localhost", name="Owner binding"),
        verify_origin=lambda value: value == BINDING_ORIGIN,
    ).authenticate_complete(state, [credential], result["assertion"])
    return credential


def parse_registry(raw, *, expected_sha256, credential_sha256, owner_sid, guardian_sid):
    """Read-only registry proof. ACL checks and its digest pin belong to deployment.

    An immutable record is not a current-key selector, revocation mechanism or
    rollback protection. Historical binding does not approve a fresh review.
    """
    if type(raw) is not bytes or not 1 <= len(raw) <= 32768:
        raise ValueError("Bounded registry bytes required")
    if hashlib.sha256(raw).hexdigest() != expected_sha256:
        raise ValueError("Independent registry digest mismatch")

    def unique(pairs):
        value = {}
        for key, item in pairs:
            if key in value:
                raise ValueError("Duplicate registry key")
            value[key] = item
        return value

    value = json.loads(raw, object_pairs_hook=unique)
    if set(value) != {
        "schema_version",
        "configuration_hex",
        "configuration_sha256",
        "manifest_sha256",
        "binding_result",
        "wrapper_sha256",
        "reset_authorized",
        "execution_available",
        "trial_started",
    }:
        raise ValueError("Exact registry fields required")
    if value["schema_version"] != "accepted-owner-credential-v1":
        raise ValueError("Registry schema mismatch")
    for flag in ("reset_authorized", "execution_available", "trial_started"):
        if value[flag] is not False:
            raise ValueError("Registry grants no activation authority")
    return verify_binding(
        value["binding_result"],
        bytes.fromhex(value["configuration_hex"]),
        configuration_sha256=value["configuration_sha256"],
        manifest_sha256=value["manifest_sha256"],
        credential_sha256=credential_sha256,
        owner_sid=owner_sid,
        guardian_sid=guardian_sid,
    )


def load_registered_guardian_config(
    configuration_path,
    *,
    registry_path,
    expected_registry_sha256,
    expected_credential_sha256,
    owner_sid,
    guardian_sid,
    **kwargs,
):
    """Native guardian admission material check only; creates no pipe or reference.

    Trusted deployment supplies the fixed record/key pins for this ceremony.
    This is not a key rotation/revocation or protected history mechanism.
    """
    from security.windows_protected_config import ProtectedConfigReader, load_guardian_config

    config = load_guardian_config(
        configuration_path, owner_sid=owner_sid, guardian_sid=guardian_sid, **kwargs
    )
    raw = ProtectedConfigReader().read_registry(
        registry_path, owner_sid=owner_sid, guardian_sid=guardian_sid
    )
    credential = parse_registry(
        raw,
        expected_sha256=expected_registry_sha256,
        credential_sha256=expected_credential_sha256,
        owner_sid=owner_sid,
        guardian_sid=guardian_sid,
    )
    if bytes(credential).hex() != config.public_credential_hex:
        raise ValueError("Guardian context credential differs from accepted registry")
    return config
