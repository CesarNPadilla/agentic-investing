"""Untrusted outbox request parsing, never owner approval or controller admission."""

import json
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class ControlRequest(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid", strict=True)
    schema_version: Literal["webull-control-request-v1"]
    action: Literal["REQUEST_READONLY_SNAPSHOT", "REQUEST_RESET_REVIEW"]
    account_binding_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    expected_state_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    request_id: str


def parse_control_request(raw: bytes, *, expected_binding: str):
    if type(raw) is not bytes or not 1 <= len(raw) <= 4096:
        raise ValueError("Bounded byte request required")
    if (
        not isinstance(expected_binding, str)
        or len(expected_binding) != 64
        or any(c not in "0123456789abcdef" for c in expected_binding)
    ):
        raise ValueError("Controller-selected account binding required")

    def unique_object(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise ValueError("Duplicate request key")
            result[key] = value
        return result

    def reject_constant(value):
        raise ValueError("Nonfinite JSON constant forbidden")

    try:
        payload = json.loads(
            raw.decode("utf-8"), object_pairs_hook=unique_object, parse_constant=reject_constant
        )
        request = ControlRequest.model_validate(payload)
        identifier = UUID(request.request_id)
        if str(identifier) != request.request_id or identifier.version != 4:
            raise ValueError("Canonical UUID4 request identifier required")
        if request.account_binding_sha256 != expected_binding:
            raise ValueError("Controller-selected account mismatch")
    except (ValueError, TypeError, UnicodeError, RecursionError):
        # Do not echo attacker-supplied text or private request contents.
        raise ValueError("Untrusted control request rejected") from None
    return request


def diagnostic_receipt(request: ControlRequest):
    """Parsing is not authentication, state reconciliation or nonce consumption."""
    return {
        "schema_version": "webull-control-request-diagnostic-v1",
        "request_id": request.request_id,
        "requested_action": request.action,
        "request_parsed": True,
        "caller_authenticated": False,
        "owner_approval_verified": False,
        "state_digest_verified": False,
        "request_replay_checked": False,
        "controller_admitted": False,
        "reset_performed": False,
        "execution_available": False,
        "trial_started": False,
    }
