"""Frozen review-consumption diagnostic; no automatic recovery or reset authority."""

import hashlib
import json
import os
import sqlite3
from contextlib import closing
from pathlib import Path


def _snapshot(journal, credential):
    with closing(sqlite3.connect(journal.path.as_uri() + "?mode=ro", uri=True)) as db:
        db.execute("BEGIN")
        if journal._verify(db, credential) != 1:
            raise ValueError("Exactly one consumed signed review required")
        rows = db.execute(
            "SELECT review_id,envelope_sha256,receipt,receipt_sha256,consumed_at FROM reviews"
        ).fetchall()
    payload = json.dumps([journal.expected_envelope.digest(), rows], separators=(",", ":"))
    return {
        "schema_version": "webull-frozen-review-checkpoint-v1",
        "envelope_sha256": journal.expected_envelope.digest(),
        "consumed_snapshot_sha256": hashlib.sha256(payload.encode()).hexdigest(),
        "retained_reviews": 1,
        "recovery_authorized": False,
        "reset_authorized": False,
        "execution_available": False,
    }


def _path(journal, checkpoint_path):
    path = Path(checkpoint_path).resolve()
    if path.parent == journal.path.parent or path == journal.path:
        raise ValueError("Separate checkpoint protection directory required")
    return path


def create_review_checkpoint(journal, credential, checkpoint_path):
    path = _path(journal, checkpoint_path)
    snapshot = _snapshot(journal, credential)
    with path.open("x", encoding="utf-8") as stream:
        stream.write(json.dumps(snapshot, sort_keys=True, allow_nan=False) + "\n")
        stream.flush()
        os.fsync(stream.fileno())
    return snapshot


def verify_review_checkpoint(journal, credential, checkpoint_path):
    path = _path(journal, checkpoint_path)
    stored = json.loads(path.read_text(encoding="utf-8"))
    if stored != _snapshot(journal, credential):
        raise ValueError("Review checkpoint mismatch; recovery blocked")
    return {
        "frozen_review_matches": True,
        "recovery_authorized": False,
        "reset_authorized": False,
        "execution_available": False,
    }
