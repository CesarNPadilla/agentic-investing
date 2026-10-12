"""Private append-only diagnostic observations, never an authoritative cash ledger."""

import hashlib
import json
import os
import sqlite3
from contextlib import closing
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4


class WebullActivityStore:
    def __init__(self, path, binding):
        if (
            not isinstance(binding, str)
            or len(binding) != 64
            or any(c not in "0123456789abcdef" for c in binding)
        ):
            raise ValueError("Account-binding digest required")
        self.path, self.binding = Path(path).resolve(), binding

    @classmethod
    def initialize(cls, path, binding):
        store = cls(path, binding)
        descriptor = os.open(store.path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
        os.close(descriptor)
        with closing(sqlite3.connect(store.path)) as db, db:
            db.execute(
                "CREATE TABLE binding (id INTEGER PRIMARY KEY CHECK(id=1), value TEXT NOT NULL)"
            )
            db.execute("INSERT INTO binding VALUES(1,?)", (binding,))
            db.execute(
                "CREATE TABLE observations (seq INTEGER PRIMARY KEY AUTOINCREMENT, observation_id TEXT UNIQUE NOT NULL, received_at TEXT NOT NULL, payload TEXT NOT NULL, digest TEXT NOT NULL)"
            )
        return store

    def _connect(self):
        return sqlite3.connect(self.path.as_uri() + "?mode=rw", uri=True, timeout=5)

    def _verify(self, db):
        if db.execute("SELECT value FROM binding WHERE id=1").fetchone() != (self.binding,):
            raise ValueError("Stored account binding mismatch")
        rows = db.execute("SELECT payload,digest FROM observations ORDER BY seq").fetchall()
        for payload, digest in rows:
            if hashlib.sha256(payload.encode()).hexdigest() != digest:
                raise ValueError("Retained observation integrity failed")
        return len(rows)

    def append(self, evidence, *, observation_id=None):
        if (
            evidence.get("schema_version") != "webull-cash-page-acquisition-v1"
            or evidence.get("execution_available") is not False
            or evidence.get("trial_started") is not False
            or evidence.get("external_flow_total") is not None
            or not isinstance(evidence.get("records"), list)
            or any(not isinstance(row, dict) for row in evidence["records"])
            or not isinstance(evidence.get("blockers"), list)
            or not {
                "ACTIVITY_PUBLICATION_UNQUALIFIED",
                "ACTIVITY_EFFECTIVE_TIME_UNQUALIFIED",
                "ACCOUNT_ASOF_UNQUALIFIED",
            }.issubset(evidence["blockers"])
        ):
            raise ValueError("Unqualified diagnostic evidence required")
        payload = json.dumps(evidence, sort_keys=True, allow_nan=False)
        if len(payload.encode()) > 1_000_000:
            raise ValueError("Diagnostic observation exceeds size bound")
        identifier = observation_id or str(uuid4())
        if not isinstance(identifier, str) or not 1 <= len(identifier) <= 100:
            raise ValueError("Observation identifier required")
        with closing(self._connect()) as db, db:
            db.execute("BEGIN IMMEDIATE")
            self._verify(db)
            db.execute(
                "INSERT INTO observations(observation_id,received_at,payload,digest) VALUES(?,?,?,?)",
                (
                    identifier,
                    datetime.now(UTC).isoformat(),
                    payload,
                    hashlib.sha256(payload.encode()).hexdigest(),
                ),
            )
        return identifier

    def verify(self):
        with closing(self._connect()) as db:
            count = self._verify(db)
        return {
            "retained_observations": count,
            "execution_available": False,
            "trial_started": False,
            "external_flow_total": None,
            "authoritative_ledger": False,
        }
