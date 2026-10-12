"""Staged owner-side write-ahead ordering; transport must be separately qualified."""

import json
from uuid import uuid4

from security.webull_review_signature import verify_review_signature


def consume_guarded_review(receipt, credential, journal, *, exchange, now):
    """Freeze/verify, guardian PREPARE, owner retention, guardian CONFIRM.

    exchange is supplied by trusted deployment code, never HTTP request data.
    A failed/lost acknowledgement retains partial state for recovery review;
    this function never retries, deletes references or grants reset authority.
    """
    if not callable(exchange):
        raise TypeError("Qualified guardian transport required")
    frozen = json.loads(json.dumps(receipt, sort_keys=True, separators=(",", ":"), allow_nan=False))
    verify_review_signature(
        frozen, credential, expected_envelope=journal.expected_envelope, now=now()
    )
    if journal.verify(credential)["retained_review_count"] != 0:
        raise ValueError("Review already retained; reconciliation required")

    def send(action, state, *, signed=None):
        request = {
            "schema_version": "webull-guardian-request-v1",
            "action": action,
            "request_id": str(uuid4()),
            "envelope_sha256": journal.expected_envelope.digest(),
        }
        if signed is not None:
            request["signed_receipt"] = signed
        raw = json.dumps(request, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()
        if len(raw) > 4096:
            raise ValueError("Guardian frame exceeds limit")
        response = exchange(raw)
        flags = {
            "owner_journal_written_by_guardian",
            "recovery_authorized",
            "reset_authorized",
            "execution_available",
            "trial_started",
        }
        if (
            type(response) is not dict
            or set(response)
            != flags | {"request_id", "reference_state", "owner_pipe_identity_observed"}
            or response["request_id"] != request["request_id"]
            or response["reference_state"] != state
            or response["owner_pipe_identity_observed"] is not True
            or any(response[flag] is not False for flag in flags)
        ):
            raise ValueError("Guardian acknowledgement rejected; reconciliation required")

    send("PREPARE_REVIEW_REFERENCE", "INTENT_RETAINED_OWNER_JOURNAL_NOT_CONSUMED", signed=frozen)
    result = journal.consume(frozen, credential, now=now())
    send("CONFIRM_REVIEW_CONSUMPTION", "MATCHING_OWNER_CONSUMPTION_CONFIRMED")
    return result | {"guardian_reference_confirmed": True}
