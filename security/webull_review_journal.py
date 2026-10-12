"""Durable one-use review evidence. No reset approval or trading authority."""

import hashlib
import json
import os
import sqlite3
from contextlib import closing
from datetime import datetime
from pathlib import Path

from security.webull_review_signature import ReviewEnvelope, verify_review_signature


def _serialize(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)


class ReviewJournal:
    def __init__(self, path, *, expected_envelope: ReviewEnvelope):
        self.path = Path(path).resolve()
        self.expected_envelope = expected_envelope

    @classmethod
    def initialize(cls, path, *, expected_envelope):
        journal = cls(path, expected_envelope=expected_envelope)
        descriptor = os.open(journal.path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
        os.close(descriptor)
        with closing(sqlite3.connect(journal.path)) as db, db:
            db.execute("CREATE TABLE context (envelope TEXT NOT NULL)")
            db.execute("INSERT INTO context VALUES(?)", (expected_envelope.model_dump_json(),))
            db.execute(
                "CREATE TABLE reviews (review_id TEXT PRIMARY KEY, envelope_sha256 TEXT UNIQUE "
                "NOT NULL, receipt TEXT NOT NULL, receipt_sha256 TEXT NOT NULL, consumed_at TEXT NOT NULL)"
            )
        return journal

    def _connect(self):
        return sqlite3.connect(self.path.as_uri() + "?mode=rw", uri=True, timeout=5)

    def _verify(self, db, credential):
        contexts = db.execute("SELECT envelope FROM context").fetchall()
        if len(contexts) != 1 or (
            ReviewEnvelope.model_validate_json(contexts[0][0]).digest()
            != self.expected_envelope.digest()
        ):
            raise ValueError("Review journal context changed")
        rows = db.execute(
            "SELECT review_id,envelope_sha256,receipt,receipt_sha256,consumed_at FROM reviews"
        ).fetchall()
        if len(rows) > 1:
            raise ValueError("Multiple consumptions of one review context")
        for review_id, envelope_digest, receipt, receipt_digest, consumed_at in rows:
            result = verify_review_signature(
                json.loads(receipt),
                credential,
                expected_envelope=self.expected_envelope,
                now=datetime.fromisoformat(consumed_at),
            )
            if (
                review_id != result["review_id"]
                or envelope_digest != result["envelope_sha256"]
                or hashlib.sha256(receipt.encode()).hexdigest() != receipt_digest
            ):
                raise ValueError("Retained review evidence changed")
        return len(rows)

    def consume(self, receipt, credential, *, now):
        # Freeze caller data before verification and persistence. A verified-result
        # boolean is never accepted in place of the original signed assertion.
        serialized = _serialize(receipt)
        frozen_receipt = json.loads(serialized)
        with closing(self._connect()) as db, db:
            db.execute("BEGIN IMMEDIATE")
            if self._verify(db, credential):
                raise ValueError("Review replay rejected")
            result = verify_review_signature(
                frozen_receipt, credential, expected_envelope=self.expected_envelope, now=now
            )
            db.execute(
                "INSERT INTO reviews VALUES(?,?,?,?,?)",
                (
                    result["review_id"],
                    result["envelope_sha256"],
                    serialized,
                    hashlib.sha256(serialized.encode()).hexdigest(),
                    now.isoformat(),
                ),
            )
        return dict(result, review_evidence_consumed=True)

    def verify(self, credential):
        with closing(self._connect()) as db, db:
            db.execute("BEGIN")
            return {
                "retained_review_count": self._verify(db, credential),
                "reset_authorized": False,
                "execution_available": False,
            }
