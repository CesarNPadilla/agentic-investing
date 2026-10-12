"""Read-only retained-review diagnosis; never repairs, retries or authorizes reset."""

import hashlib
import json
from datetime import datetime
from uuid import UUID

from security.webull_review_signature import verify_review_signature


def _read(path):
    if (
        path.is_symlink()
        or path.is_junction()
        or getattr(path.stat(), "st_file_attributes", 0) & 0x400
    ):
        raise ValueError("Ordinary retained reference file required")
    if not 1 <= path.stat().st_size <= 65536:
        raise ValueError("Bounded retained reference required")
    raw = path.read_bytes()

    def unique(pairs):
        value = {}
        for key, item in pairs:
            if key in value:
                raise ValueError("Duplicate retained reference key")
            value[key] = item
        return value

    def reject_constant(_):
        raise ValueError("Nonfinite retained reference")

    value = json.loads(
        raw.decode("utf-8"), object_pairs_hook=unique, parse_constant=reject_constant
    )
    if type(value) is not dict:
        raise ValueError("Retained reference object required")
    return raw, value


def _identifier(value):
    identifier = UUID(value)
    if identifier.version != 4 or str(identifier) != value:
        raise ValueError("Canonical retained request identifier required")


def inspect_guardian_review(reference, *, now, expected_intent_sha256=None):
    """Expected digest, if supplied, must come from separately protected state.

    This is a local diagnostic snapshot. It does not prove durable filesystem
    ordering, trustworthy clocks, OS isolation or broker accounting completeness.
    Missing records never establish a fresh usable review context.
    """
    if now.tzinfo is None or now.utcoffset() is None:
        raise ValueError("Aware diagnostic clock required")
    if expected_intent_sha256 is not None and (
        type(expected_intent_sha256) is not str
        or len(expected_intent_sha256) != 64
        or any(char not in "0123456789abcdef" for char in expected_intent_sha256)
    ):
        raise ValueError("Expected intent digest invalid")
    rows = reference._rows()
    presence = {path: path.exists() for path in (reference.intent, reference.confirmation)}
    snapshots = {}
    if not reference.intent.exists():
        if rows or reference.confirmation.exists() or expected_intent_sha256 is not None:
            raise ValueError("Missing guardian intent; reconciliation blocked")
        state = "NO_RETAINED_EVIDENCE_FRESHNESS_UNESTABLISHED"
    else:
        raw, intent = _read(reference.intent)
        snapshots[reference.intent] = raw
        intent_digest = hashlib.sha256(raw).hexdigest()
        if expected_intent_sha256 is not None and expected_intent_sha256 != intent_digest:
            raise ValueError("Protected expected intent digest mismatch")
        if set(intent) != {
            "schema_version",
            "request_id",
            "envelope_sha256",
            "prepared_at",
            "receipt_sha256",
            "signed_receipt",
        } or (
            intent["schema_version"] != "webull-guardian-intent-v1"
            or intent["envelope_sha256"] != reference.journal.expected_envelope.digest()
        ):
            raise ValueError("Guardian intent context changed")
        _identifier(intent["request_id"])
        prepared = datetime.fromisoformat(intent["prepared_at"])
        if prepared.tzinfo is None or prepared.utcoffset() is None or prepared > now:
            raise ValueError("Guardian preparation time invalid")
        verify_review_signature(
            intent["signed_receipt"],
            reference.credential,
            expected_envelope=reference.journal.expected_envelope,
            now=prepared,
        )
        serialized = json.dumps(
            intent["signed_receipt"], sort_keys=True, separators=(",", ":"), allow_nan=False
        )
        if hashlib.sha256(serialized.encode()).hexdigest() != intent["receipt_sha256"]:
            raise ValueError("Retained receipt digest mismatch")
        if not rows:
            if reference.confirmation.exists():
                raise ValueError("Confirmation without matching consumption")
            state = "INTENT_ONLY_RECONCILIATION_REQUIRED"
        else:
            if (
                len(rows) != 1
                or rows[0][0] != intent["receipt_sha256"]
                or not prepared <= datetime.fromisoformat(rows[0][1]) <= now
            ):
                raise ValueError("Matching owner consumption not established")
            if not reference.confirmation.exists():
                state = "MATCHING_CONSUMPTION_CONFIRMATION_PENDING"
            else:
                confirmation_raw, confirmation = _read(reference.confirmation)
                snapshots[reference.confirmation] = confirmation_raw
                if set(confirmation) != {
                    "schema_version",
                    "request_id",
                    "intent_sha256",
                    "receipt_sha256",
                    "consumed_at",
                    "reset_authorized",
                    "execution_available",
                } or (
                    confirmation["schema_version"] != "webull-guardian-confirmation-v1"
                    or confirmation["request_id"] == intent["request_id"]
                    or confirmation["intent_sha256"] != intent_digest
                    or confirmation["receipt_sha256"] != rows[0][0]
                    or confirmation["consumed_at"] != rows[0][1]
                    or confirmation["reset_authorized"] is not False
                    or confirmation["execution_available"] is not False
                ):
                    raise ValueError("Guardian confirmation changed")
                _identifier(confirmation["request_id"])
                state = "MATCHING_RETAINED_REVIEW_NO_RESET_AUTHORITY"
    if (
        reference._rows() != rows
        or any(path.exists() != existed for path, existed in presence.items())
        or any(path.read_bytes() != raw for path, raw in snapshots.items())
    ):
        raise ValueError("Review evidence changed during inspection")
    return {
        "schema_version": "webull-guardian-recovery-inspection-v1",
        "observed_at": now.isoformat(),
        "reference_state": state,
        "retained_review_count": len(rows),
        "expected_intent_digest_matched": expected_intent_sha256 is not None,
        "files_written": False,
        "journal_written": False,
        "automatic_retry_available": False,
        "recovery_authorized": False,
        "reset_authorized": False,
        "execution_available": False,
        "trial_started": False,
    }
