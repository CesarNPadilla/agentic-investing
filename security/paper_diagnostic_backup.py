"""Private diagnostic ledger snapshots; no restore, reset or execution authority."""

import hashlib
import os
import sqlite3
import time
from contextlib import closing
from pathlib import Path

from risk.paper_state import PaperState


def create_diagnostic_backup(source, destination, *, repository_root):
    source, destination = Path(source).resolve(), Path(destination).resolve()
    root = Path(repository_root).resolve()
    if source.is_relative_to(root) or destination.is_relative_to(root):
        raise ValueError("Diagnostic state must remain private")
    if source == destination or not source.is_file():
        raise ValueError("Distinct existing source required")
    # Reject a corrupt source before creating a destination.
    with closing(sqlite3.connect(source.as_uri() + "?mode=ro", uri=True)) as db:
        row = db.execute("SELECT payload,digest FROM state WHERE id=1").fetchone()
        if row is None or hashlib.sha256(row[0].encode()).hexdigest() != row[1]:
            raise ValueError("Source state integrity failed")
    # Exclusive creation preserves every pre-existing destination.
    descriptor = os.open(destination, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    os.close(descriptor)
    deadline = time.monotonic() + 10

    def progress(status, remaining, total):
        if time.monotonic() > deadline:
            raise RuntimeError("Diagnostic snapshot deadline exceeded")

    with (
        closing(sqlite3.connect(source.as_uri() + "?mode=ro", uri=True)) as original,
        closing(sqlite3.connect(destination)) as backup,
    ):
        original.backup(backup, pages=32, progress=progress, sleep=0.01)
        if backup.execute("PRAGMA integrity_check").fetchone() != ("ok",):
            raise ValueError("Snapshot integrity failed")
    state = PaperState(destination).read()
    # PaperState enforces digest, budget and latched/nonexecuting invariants.
    with destination.open("r+b") as handle:
        os.fsync(handle.fileno())
    return {
        "status": "VERIFIED_DIAGNOSTIC_SNAPSHOT",
        "snapshot_sha256": hashlib.sha256(destination.read_bytes()).hexdigest(),
        "latched": state["latched"],
        "execution_available": False,
        "trial_started": False,
        "restore_authorized": False,
    }
