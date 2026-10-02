"""Dedicated SQLite synthetic journal. No production DB, reset API or broker IO."""
import hashlib
import json
import sqlite3
from contextlib import closing, contextmanager
from pathlib import Path

from risk.sleeve_v11 import SleeveDiagnostic, SyntheticSleeveInput, evaluate_synthetic_sleeve


class SyntheticStoreError(RuntimeError):
    """Persistence is unavailable or inconsistent; callers must block."""


def _hash(previous: str, payload: str) -> str:
    return hashlib.sha256((previous + "\n" + payload).encode("utf-8")).hexdigest()


class SyntheticSleeveStore:
    """Explicit isolated test store with atomic append and monotonic latch.

    Opening never creates missing state. Initialization is explicit, refuses any
    existing tables, and starts latched by default. Test fixtures may explicitly
    initialize an unlatched store. There is deliberately no reset operation.
    Hash chaining detects accidental/out-of-band edits, not a malicious DB owner
    able to rewrite the entire chain. No external trust anchor is claimed.
    """
    def __init__(self, path: Path):
        self.path = Path(path)

    @classmethod
    def initialize(cls, path: Path, *, synthetic_initial_latched: bool = True):
        if type(synthetic_initial_latched) is not bool:
            raise SyntheticStoreError("Synthetic initial latch must be explicit boolean")
        store = cls(path)
        try:
            with closing(sqlite3.connect(store.path, timeout=10)) as db, db:
                db.execute("BEGIN IMMEDIATE")
                if db.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchone():
                    raise SyntheticStoreError("Refusing to initialize an existing database")
                db.execute("CREATE TABLE journal (seq INTEGER PRIMARY KEY, payload TEXT NOT NULL, "
                           "previous TEXT NOT NULL, digest TEXT NOT NULL)")
                payload = json.dumps({"kind": "SYNTHETIC_BOOTSTRAP", "latched":
                                      bool(synthetic_initial_latched)}, sort_keys=True)
                db.execute("INSERT INTO journal VALUES (1, ?, ?, ?)",
                           (payload, "", _hash("", payload)))
        except sqlite3.Error as exc:
            raise SyntheticStoreError("Synthetic persistence unavailable") from exc
        return store

    @contextmanager
    def _connect(self):
        try:
            # mode=rw refuses to silently recreate a missing state database.
            with closing(sqlite3.connect(self.path.resolve().as_uri() + "?mode=rw",
                                         uri=True, timeout=10)) as db, db:
                tables = {row[0] for row in db.execute(
                    "SELECT name FROM sqlite_master WHERE type='table'")}
                if tables != {"journal"}:
                    raise SyntheticStoreError("Not an isolated synthetic database")
                yield db
        except sqlite3.Error as exc:
            raise SyntheticStoreError("Synthetic persistence unavailable") from exc

    @staticmethod
    def _verify(db):
        rows = db.execute("SELECT seq, payload, previous, digest FROM journal ORDER BY seq").fetchall()
        if not rows:
            raise SyntheticStoreError("Missing persisted synthetic state")
        previous = ""
        latched = False
        for index, (seq, payload, prior, digest) in enumerate(rows, 1):
            if seq != index or prior != previous or digest != _hash(prior, payload):
                raise SyntheticStoreError("Synthetic journal integrity failure")
            event = json.loads(payload)
            if index == 1:
                if event.get("kind") != "SYNTHETIC_BOOTSTRAP" or type(event.get("latched")) is not bool:
                    raise SyntheticStoreError("Invalid synthetic bootstrap")
                latched = event["latched"]
            else:
                if event.get("kind") != "SYNTHETIC_DIAGNOSTIC":
                    raise SyntheticStoreError("Invalid synthetic journal event")
                data = SyntheticSleeveInput.model_validate_json(event["input"])
                result = SleeveDiagnostic.model_validate_json(event["result"])
                if latched and not data.kill_switch_latched:
                    raise SyntheticStoreError("Persisted latch was bypassed")
                if evaluate_synthetic_sleeve(data) != result:
                    raise SyntheticStoreError("Synthetic replay mismatch")
                latched = latched or result.persistent_latch_required
            previous = digest
        return len(rows), previous, latched

    def latched(self) -> bool:
        try:
            with self._connect() as db:
                db.execute("BEGIN")
                return self._verify(db)[2]
        except (sqlite3.Error, ValueError, KeyError, TypeError) as exc:
            raise SyntheticStoreError("Synthetic state cannot be verified") from exc

    def evaluate_and_record(self, data: SyntheticSleeveInput) -> SleeveDiagnostic:
        try:
            with self._connect() as db:
                db.execute("BEGIN IMMEDIATE")
                count, previous, latched = self._verify(db)
                effective = data.model_copy(update={"kill_switch_latched":
                                                   latched or data.kill_switch_latched})
                result = evaluate_synthetic_sleeve(effective)
                payload = json.dumps({"kind": "SYNTHETIC_DIAGNOSTIC",
                                      "input": effective.model_dump_json(),
                                      "result": result.model_dump_json()}, sort_keys=True)
                db.execute("INSERT INTO journal VALUES (?, ?, ?, ?)",
                           (count + 1, payload, previous, _hash(previous, payload)))
                return result
        except (sqlite3.Error, ValueError, KeyError, TypeError) as exc:
            raise SyntheticStoreError("Synthetic evaluation could not be persisted") from exc
