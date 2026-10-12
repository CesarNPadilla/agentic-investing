"""Staged durable request registration; no approval, reset or broker authority."""

import hashlib
import json
import os
import sqlite3
from contextlib import closing
from datetime import UTC, datetime
from pathlib import Path

from security.webull_control_request import diagnostic_receipt, parse_control_request


def _digest(value):
    if (
        not isinstance(value, str)
        or len(value) != 64
        or any(c not in "0123456789abcdef" for c in value)
    ):
        raise ValueError("SHA256 binding required")
    return value


class RequestJournal:
    def __init__(self, path, binding):
        self.path, self.binding = Path(path).resolve(), _digest(binding)

    @classmethod
    def initialize(cls, path, binding, *, state_digest):
        journal = cls(path, binding)
        state_digest = _digest(state_digest)
        descriptor = os.open(journal.path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
        os.close(descriptor)
        with closing(sqlite3.connect(journal.path)) as db, db:
            db.execute(
                "CREATE TABLE context (id INTEGER PRIMARY KEY CHECK(id=1), binding TEXT NOT NULL, state_digest TEXT NOT NULL)"
            )
            db.execute("INSERT INTO context VALUES(1,?,?)", (binding, state_digest))
            db.execute(
                "CREATE TABLE requests (request_id TEXT PRIMARY KEY, request TEXT NOT NULL, receipt TEXT NOT NULL, receipt_sha256 TEXT NOT NULL)"
            )
        return journal

    def _connect(self):
        return sqlite3.connect(self.path.as_uri() + "?mode=rw", uri=True, timeout=5)

    def _context(self, db):
        rows = db.execute("SELECT binding,state_digest FROM context").fetchall()
        if len(rows) != 1 or rows[0][0] != self.binding:
            raise ValueError("Journal account binding mismatch")
        state_digest = _digest(rows[0][1])
        for request_id, request, receipt, digest in db.execute(
            "SELECT request_id,request,receipt,receipt_sha256 FROM requests"
        ):
            parsed = parse_control_request(request.encode(), expected_binding=self.binding)
            stored = json.loads(receipt)
            if (
                hashlib.sha256(receipt.encode()).hexdigest() != digest
                or parsed.request_id != request_id
                or stored.get("request_id") != request_id
                or stored.get("request_sha256") != hashlib.sha256(request.encode()).hexdigest()
                or stored.get("requested_action") != parsed.action
                or stored.get("controller_admitted") is not False
                or stored.get("reset_performed") is not False
                or stored.get("execution_available") is not False
                or stored.get("trial_started") is not False
            ):
                raise ValueError("Retained journal evidence invalid")
        return state_digest

    def register(self, raw, *, caller_identity_sha256=None):
        if caller_identity_sha256 is not None:
            _digest(caller_identity_sha256)
        request = parse_control_request(raw, expected_binding=self.binding)
        with closing(self._connect()) as db, db:
            db.execute("BEGIN IMMEDIATE")
            state_digest = self._context(db)
            if db.execute(
                "SELECT 1 FROM requests WHERE request_id=?", (request.request_id,)
            ).fetchone():
                raise ValueError("Request replay rejected")
            receipt = diagnostic_receipt(request)
            serialized_request = request.model_dump_json()
            matches = request.expected_state_sha256 == state_digest
            receipt.update(
                schema_version="webull-request-registration-v1",
                request_replay_checked=True,
                request_registered=True,
                expected_state_matches=matches,
                registered_at_utc=datetime.now(UTC).isoformat(),
                request_sha256=hashlib.sha256(serialized_request.encode()).hexdigest(),
                caller_identity_sha256=caller_identity_sha256,
                blockers=[
                    "CALLER_AUTHENTICATION_UNQUALIFIED",
                    "OWNER_APPROVAL_UNQUALIFIED",
                    "PROTECTED_CONTROLLER_DEPLOYMENT_PENDING",
                    "STATE_SOURCE_UNQUALIFIED",
                ]
                + ([] if matches else ["EXPECTED_STATE_CHANGED"]),
            )
            # A digest match alone never qualifies source state or reset prerequisites.
            serialized = json.dumps(receipt, sort_keys=True, allow_nan=False)
            db.execute(
                "INSERT INTO requests VALUES(?,?,?,?)",
                (
                    request.request_id,
                    serialized_request,
                    serialized,
                    hashlib.sha256(serialized.encode()).hexdigest(),
                ),
            )
        return receipt

    def verify(self):
        with closing(self._connect()) as db:
            db.execute("BEGIN")
            self._context(db)
            count = db.execute("SELECT COUNT(*) FROM requests").fetchone()[0]
        return {
            "retained_requests": count,
            "controller_admitted": False,
            "reset_performed": False,
            "execution_available": False,
        }
