"""Frozen diagnostic checkpoint; never authorizes recovery or journal advancement."""

import hashlib
import json
import os
import sqlite3
from contextlib import closing
from pathlib import Path

from security.webull_request_journal import RequestJournal


def _snapshot(journal):
    # Hash and inspect one consistent SQLite snapshot, rather than the live file.
    with closing(sqlite3.connect(journal.path.as_uri() + "?mode=ro", uri=True)) as db:
        db.execute("BEGIN")
        state = journal._context(db)
        rows = db.execute(
            "SELECT request_id,request,receipt,receipt_sha256 FROM requests ORDER BY request_id"
        ).fetchall()
    serialized = json.dumps([journal.binding, state, rows], separators=(",", ":"))
    return {
        "schema_version": "webull-frozen-journal-checkpoint-v1",
        "account_binding_sha256": journal.binding,
        "snapshot_sha256": hashlib.sha256(serialized.encode()).hexdigest(),
        "retained_requests": len(rows),
        "recovery_authorized": False,
        "execution_available": False,
    }


def _separate_path(journal, checkpoint_path):
    path = Path(checkpoint_path).resolve()
    if path.parent == journal.path.parent or path == journal.path:
        raise ValueError("Checkpoint requires a separate protection directory")
    return path


def create_frozen_checkpoint(journal: RequestJournal, checkpoint_path):
    path = _separate_path(journal, checkpoint_path)
    snapshot = _snapshot(journal)
    # Exclusive creation: a diagnostic rerun cannot replace the old reference.
    with path.open("x", encoding="utf-8") as stream:
        stream.write(json.dumps(snapshot, sort_keys=True, allow_nan=False) + "\n")
        stream.flush()
        os.fsync(stream.fileno())
    return snapshot


def verify_frozen_checkpoint(journal: RequestJournal, checkpoint_path):
    path = _separate_path(journal, checkpoint_path)
    checkpoint = json.loads(path.read_text(encoding="utf-8"))
    current = _snapshot(journal)
    if json.dumps(checkpoint, sort_keys=True, allow_nan=False) != json.dumps(
        current, sort_keys=True, allow_nan=False
    ):
        raise ValueError("Frozen checkpoint mismatch; recovery remains blocked")
    return {
        "frozen_snapshot_matches": True,
        "retained_requests": current["retained_requests"],
        "recovery_authorized": False,
        "execution_available": False,
    }
