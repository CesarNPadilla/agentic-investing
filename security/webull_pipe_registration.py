"""Staged pipe identity-to-request-journal bridge; no owner approval or reset."""

import hashlib
import re

from security.windows_pipe_identity import identify_pipe_client


def register_connected_request(handle, raw, journal, *, owner_sid, runtime_sid, identity_api=None):
    """Trusted transport must supply bytes just read on this same connected handle.

    Trusted owner/runtime SID configuration must come from the protected controller,
    never from the request. This helper does not create or qualify that transport.
    """
    if (
        not isinstance(owner_sid, str)
        or not isinstance(runtime_sid, str)
        or not re.fullmatch(r"S-1-(?:[0-9]+-)*[0-9]+", owner_sid)
        or not re.fullmatch(r"S-1-(?:[0-9]+-)*[0-9]+", runtime_sid)
        or owner_sid == runtime_sid
    ):
        raise ValueError("Distinct protected owner/runtime identity configuration required")
    sid = identify_pipe_client(handle, api=identity_api)
    # identify_pipe_client has already reverted; persistence never runs as the client.
    if sid not in (owner_sid, runtime_sid):
        raise PermissionError("Pipe caller outside configured request scope")
    receipt = journal.register(raw, caller_identity_sha256=hashlib.sha256(sid.encode()).hexdigest())
    return receipt | {
        "observed_caller_role": "OWNER" if sid == owner_sid else "RUNTIME",
        "owner_approval_verified": False,
        "controller_admitted": False,
        "reset_performed": False,
        "execution_available": False,
        "trial_started": False,
    }
