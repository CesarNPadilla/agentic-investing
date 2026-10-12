"""Staged write-ahead one-use review evidence; no recovery/reset admission."""

import hashlib
import json
import os
import sqlite3
from contextlib import closing
from pathlib import Path

from security.webull_review_signature import verify_review_signature


class ReviewIntent:
    def __init__(self, journal, intent_file):
        self.journal = journal
        self.intent = Path(intent_file).resolve()
        if self.intent.parent.is_relative_to(
            journal.path.parent
        ) or journal.path.parent.is_relative_to(self.intent.parent):
            raise ValueError("Independent reference directory required")
        self.bootstrap = self.intent.with_suffix(".provisioned.json")

    @classmethod
    def initialize(cls, journal, intent_file, credential):
        guard = cls(journal, intent_file)
        if guard.intent.exists() or guard._rows(credential):
            raise ValueError("Only fresh unconsumed context can provision a reference")
        guard._exclusive(guard.bootstrap, guard._context())
        return guard

    def _context(self):
        return {
            "schema_version": "webull-review-intent-reference-v1",
            "envelope_sha256": self.journal.expected_envelope.digest(),
            "reset_authorized": False,
            "execution_available": False,
        }

    @staticmethod
    def _exclusive(path, record):
        with path.open("x", encoding="utf-8") as stream:
            stream.write(json.dumps(record, sort_keys=True, allow_nan=False) + "\n")
            stream.flush()
            os.fsync(stream.fileno())

    def _rows(self, credential):
        with closing(sqlite3.connect(self.journal.path.as_uri() + "?mode=ro", uri=True)) as db:
            db.execute("BEGIN")
            self.journal._verify(db, credential)
            return db.execute("SELECT receipt_sha256,consumed_at FROM reviews").fetchall()

    def inspect(self, credential):
        if json.loads(self.bootstrap.read_text(encoding="utf-8")) != self._context():
            raise ValueError("Reference context changed")
        rows = self._rows(credential)
        if not self.intent.exists():
            if rows:
                raise ValueError("Consumed review has no write-ahead reference")
            state = "FRESH_REFERENCE_ONLY"
        else:
            intent = json.loads(self.intent.read_text(encoding="utf-8"))
            if set(intent) != {"context", "receipt_sha256", "consumed_at"} or (
                intent["context"] != self._context()
            ):
                raise ValueError("Intent reference invalid")
            state = (
                "CONSUMED_REVIEW_MATCHES_REFERENCE"
                if rows == [(intent["receipt_sha256"], intent["consumed_at"])]
                else "INCOMPLETE_OR_ROLLED_BACK_BLOCKED"
            )
        return {
            "state": state,
            "recovery_authorized": False,
            "reset_authorized": False,
            "execution_available": False,
        }

    def consume(self, receipt, credential, *, now):
        serialized = json.dumps(receipt, sort_keys=True, separators=(",", ":"), allow_nan=False)
        frozen = json.loads(serialized)
        if self.inspect(credential)["state"] != "FRESH_REFERENCE_ONLY":
            raise ValueError("Used or incomplete intent; retry blocked")
        verify_review_signature(
            frozen, credential, expected_envelope=self.journal.expected_envelope, now=now
        )
        # Exclusive durable intent precedes the SQLite write. Any later failure
        # retains this evidence and blocks retries; there is no automatic cleanup.
        self._exclusive(
            self.intent,
            {
                "context": self._context(),
                "receipt_sha256": hashlib.sha256(serialized.encode()).hexdigest(),
                "consumed_at": now.isoformat(),
            },
        )
        result = self.journal.consume(frozen, credential, now=now)
        if self.inspect(credential)["state"] != "CONSUMED_REVIEW_MATCHES_REFERENCE":
            raise ValueError("Post-consumption reference mismatch")
        return dict(result, write_ahead_intent_retained=True)
