"""Staged guardian-only intent and confirmation; never writes the owner journal."""

import hashlib
import json
import os
import sqlite3
from contextlib import closing
from datetime import datetime
from pathlib import Path
from uuid import UUID

from security.webull_review_signature import verify_review_signature


def parse_guardian_request(raw, expected_digest):
    if type(raw) is not bytes or not 1 <= len(raw) <= 4096:
        raise ValueError("Bounded guardian request required")

    def unique(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise ValueError("Duplicate key")
            result[key] = value
        return result

    def reject_constant(_):
        raise ValueError("Nonfinite JSON")

    try:
        value = json.loads(
            raw.decode("utf-8"), object_pairs_hook=unique, parse_constant=reject_constant
        )
        if not isinstance(value, dict) or value.get("action") not in {
            "PREPARE_REVIEW_REFERENCE",
            "CONFIRM_REVIEW_CONSUMPTION",
        }:
            raise ValueError("Wrong action")
        keys = {"schema_version", "action", "request_id", "envelope_sha256"}
        if value["action"] == "PREPARE_REVIEW_REFERENCE":
            keys.add("signed_receipt")
        identifier = UUID(value["request_id"])
        if (
            set(value) != keys
            or value["schema_version"] != "webull-guardian-request-v1"
            or value["envelope_sha256"] != expected_digest
            or identifier.version != 4
            or str(identifier) != value["request_id"]
        ):
            raise ValueError("Wrong context")
    except (ValueError, TypeError, KeyError, AttributeError, UnicodeError, RecursionError):
        raise ValueError("Guardian request rejected") from None
    return value


class GuardianReference:
    def __init__(self, directory, journal, credential):
        self.directory, self.journal, self.credential = (
            Path(directory).resolve(),
            journal,
            credential,
        )
        if self.directory.is_relative_to(journal.path.parent) or journal.path.parent.is_relative_to(
            self.directory
        ):
            raise ValueError("Separate guardian reference directory required")
        self.intent = self.directory / "intent.json"
        self.confirmation = self.directory / "confirmation.json"

    def _rows(self):
        # Read-only connection, with cryptographic verification of owner journal rows.
        with closing(sqlite3.connect(self.journal.path.as_uri() + "?mode=ro", uri=True)) as db:
            db.execute("BEGIN")
            self.journal._verify(db, self.credential)
            return db.execute("SELECT receipt_sha256,consumed_at FROM reviews").fetchall()

    @staticmethod
    def _exclusive(path, record):
        with path.open("x", encoding="utf-8") as stream:
            stream.write(json.dumps(record, sort_keys=True, allow_nan=False) + "\n")
            stream.flush()
            os.fsync(stream.fileno())

    def handle(self, raw, *, now):
        if now.tzinfo is None or now.utcoffset() is None:
            raise ValueError("Aware guardian clock required")
        request = parse_guardian_request(raw, self.journal.expected_envelope.digest())
        if request["action"] == "PREPARE_REVIEW_REFERENCE":
            if self._rows() or self.intent.exists() or self.confirmation.exists():
                raise ValueError("Used or inconsistent reference context")
            receipt = request["signed_receipt"]
            verify_review_signature(
                receipt, self.credential, expected_envelope=self.journal.expected_envelope, now=now
            )
            serialized = json.dumps(receipt, sort_keys=True, separators=(",", ":"), allow_nan=False)
            self._exclusive(
                self.intent,
                {
                    "schema_version": "webull-guardian-intent-v1",
                    "request_id": request["request_id"],
                    "envelope_sha256": self.journal.expected_envelope.digest(),
                    "prepared_at": now.isoformat(),
                    "receipt_sha256": hashlib.sha256(serialized.encode()).hexdigest(),
                    "signed_receipt": receipt,
                },
            )
            state = "INTENT_RETAINED_OWNER_JOURNAL_NOT_CONSUMED"
        else:
            intent = json.loads(self.intent.read_text(encoding="utf-8"))
            if set(intent) != {
                "schema_version",
                "request_id",
                "envelope_sha256",
                "prepared_at",
                "receipt_sha256",
                "signed_receipt",
            } or (
                intent["schema_version"] != "webull-guardian-intent-v1"
                or intent["envelope_sha256"] != self.journal.expected_envelope.digest()
                or intent["request_id"] == request["request_id"]
            ):
                raise ValueError("Guardian reference changed")
            prepared = datetime.fromisoformat(intent["prepared_at"])
            verify_review_signature(
                intent["signed_receipt"],
                self.credential,
                expected_envelope=self.journal.expected_envelope,
                now=prepared,
            )
            serialized = json.dumps(
                intent["signed_receipt"], sort_keys=True, separators=(",", ":"), allow_nan=False
            )
            if hashlib.sha256(serialized.encode()).hexdigest() != intent["receipt_sha256"]:
                raise ValueError("Changed retained receipt")
            rows = self._rows()
            if (
                len(rows) != 1
                or rows[0][0] != intent["receipt_sha256"]
                or not (prepared <= datetime.fromisoformat(rows[0][1]) <= now)
            ):
                raise ValueError("Owner journal does not prove matching consumption")
            self._exclusive(
                self.confirmation,
                {
                    "schema_version": "webull-guardian-confirmation-v1",
                    "request_id": request["request_id"],
                    "intent_sha256": hashlib.sha256(self.intent.read_bytes()).hexdigest(),
                    "receipt_sha256": rows[0][0],
                    "consumed_at": rows[0][1],
                    "reset_authorized": False,
                    "execution_available": False,
                },
            )
            state = "MATCHING_OWNER_CONSUMPTION_CONFIRMED"
        return {
            "request_id": request["request_id"],
            "reference_state": state,
            "owner_journal_written_by_guardian": False,
            "recovery_authorized": False,
            "reset_authorized": False,
            "execution_available": False,
            "trial_started": False,
        }
