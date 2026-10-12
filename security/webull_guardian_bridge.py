"""Connected-pipe identity boundary for guardian reference requests; no service."""

import re

from security.windows_pipe_identity import NativePipeIdentity, identify_pipe_client


def dispatch_guardian_connected(
    handle, raw, reference, *, guardian_sid, owner_sid, now, identity_api=None
):
    """Only trusted transport supplies this handle and its just-read bytes.

    Role configuration and clock belong to protected guardian configuration,
    not to the payload. This helper does not create a transport or service.
    """
    if guardian_sid == owner_sid or not all(
        isinstance(value, str) and re.fullmatch(r"S-1-(?:[0-9]+-)*[0-9]+", value)
        for value in (guardian_sid, owner_sid)
    ):
        raise ValueError("Distinct configured identities required")
    api = identity_api or NativePipeIdentity()
    if api.read_process_identity() != guardian_sid:
        raise PermissionError("Guardian process identity mismatch")
    caller = identify_pipe_client(handle, api=api)
    # Identification restores server identity before any reference write.
    if caller != owner_sid:
        raise PermissionError("Only configured owner may request a review reference")
    return reference.handle(raw, now=now) | {"owner_pipe_identity_observed": True}
