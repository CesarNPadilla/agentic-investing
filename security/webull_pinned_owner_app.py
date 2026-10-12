"""Pinned owner UI construction; deployment, transport and passkey remain separate."""

import ctypes
from ctypes import wintypes
from datetime import UTC, datetime

from fido2.webauthn import AttestedCredentialData

from security.webull_guardian_host_config import parse_pinned_host_config
from security.webull_owner_review_app import create_app
from security.webull_review_journal import ReviewJournal
from security.windows_pipe_identity import NativePipeIdentity
from security.windows_protected_config import ProtectedConfigReader


def require_standard_owner(owner_sid):
    api = NativePipeIdentity()
    if api.read_process_identity() != owner_sid:
        raise PermissionError("Configured owner process required")
    token, elevation, used = wintypes.HANDLE(), wintypes.DWORD(), wintypes.DWORD()
    if not api.security.OpenProcessToken(api.kernel.GetCurrentProcess(), 8, ctypes.byref(token)):
        raise OSError("Owner token unavailable")
    try:
        if (
            not api.security.GetTokenInformation(
                token, 20, ctypes.byref(elevation), 4, ctypes.byref(used)
            )
            or used.value != 4
            or elevation.value
        ):
            raise PermissionError("Standard owner token required")
    finally:
        api.kernel.CloseHandle(token)


def create_pinned_owner_app(
    configuration_path,
    *,
    owner_sid,
    guardian_sid,
    expected_sha256,
    expected_manifest_sha256,
    guardian_exchange,
    now=None,
    credential_loader=None,
):
    """Deployment supplies trusted pins and an authenticated bounded exchange.

    No host is started here. This factory does not attest that an injected callable
    is a qualified transport. Native protected reads retain the existing loader's
    administrator/prior-mapping/rollback limitations and require outer supervision.
    """
    if not callable(guardian_exchange):
        raise TypeError("Explicit guardian exchange required")
    now = now or (lambda: datetime.now(UTC))

    def context():
        # Recheck token, held-handle ACLs, pinned bytes and expiry for each request.
        require_standard_owner(owner_sid)
        raw = ProtectedConfigReader().read(
            configuration_path, owner_sid=owner_sid, guardian_sid=guardian_sid
        )
        config = parse_pinned_host_config(
            raw,
            expected_sha256=expected_sha256,
            expected_manifest_sha256=expected_manifest_sha256,
            now=now(),
        )
        if config.owner_sid != owner_sid or config.guardian_sid != guardian_sid:
            raise ValueError("Protected owner configuration roles mismatch")
        credential = AttestedCredentialData(bytes.fromhex(config.public_credential_hex))
        if credential_loader is not None and bytes(credential_loader()) != bytes(credential):
            raise ValueError("Review credential differs from accepted registry")
        journal = ReviewJournal(config.journal_path, expected_envelope=config.envelope)
        if journal.verify(credential)["retained_review_count"]:
            raise ValueError("Review already consumed")
        return config.envelope, credential, journal

    context()  # Reject before serving HTTP or issuing any challenge.
    return create_app(
        None, None, None, now=now, guardian_exchange=guardian_exchange, context_loader=context
    )


def create_registered_owner_app(
    configuration_path,
    *,
    registry_path,
    expected_registry_sha256,
    expected_credential_sha256,
    owner_sid,
    guardian_sid,
    **kwargs,
):
    """Registry-enforcing review entry point; deployment independently supplies pins.

    Legacy construction remains for isolated synthetic fixtures. This factory
    never selects a key from owner-writable enrollment or HTTP input.
    """
    from security.webull_owner_credential_registry import parse_registry

    if "credential_loader" in kwargs:
        raise ValueError("Fixed registry credential loader required")

    def credential_loader():
        raw = ProtectedConfigReader().read_registry(
            registry_path, owner_sid=owner_sid, guardian_sid=guardian_sid
        )
        return parse_registry(
            raw,
            expected_sha256=expected_registry_sha256,
            credential_sha256=expected_credential_sha256,
            owner_sid=owner_sid,
            guardian_sid=guardian_sid,
        )

    return create_pinned_owner_app(
        configuration_path,
        owner_sid=owner_sid,
        guardian_sid=guardian_sid,
        credential_loader=credential_loader,
        **kwargs,
    )
