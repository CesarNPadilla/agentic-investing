"""Isolated durable paper preparation state, no broker mutations or reset authority."""

import hashlib
import json
import sqlite3
from contextlib import closing, contextmanager
from decimal import Decimal
from pathlib import Path


class PaperStateError(RuntimeError):
    pass


def amount(value, *, positive=False):
    value = Decimal(str(value))
    if not value.is_finite() or value < 0 or (positive and value == 0):
        raise PaperStateError("Invalid amount")
    return value


class PaperState:
    def __init__(self, path):
        self.path = Path(path)

    @classmethod
    def initialize(cls, path, *, account_binding, budget="1000"):
        budget = amount(budget, positive=True)
        if (
            budget > 1000
            or len(account_binding) != 64
            or any(c not in "0123456789abcdef" for c in account_binding)
        ):
            raise PaperStateError("Invalid budget or account binding")
        store = cls(path)
        with closing(sqlite3.connect(store.path, timeout=10)) as db, db:
            db.execute("BEGIN IMMEDIATE")
            if db.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchone():
                raise PaperStateError("Refusing existing database")
            db.execute(
                "CREATE TABLE state (id INTEGER PRIMARY KEY CHECK(id=1), payload TEXT NOT NULL, digest TEXT NOT NULL)"
            )
            payload = json.dumps(
                {
                    "binding": account_binding,
                    "budget": str(budget),
                    "latched": True,
                    "latch_reasons": ["INITIAL_REVIEW_REQUIRED"],
                    "reservations": {},
                    "observations": [],
                    "execution_available": False,
                },
                sort_keys=True,
            )
            db.execute(
                "INSERT INTO state VALUES (1,?,?)",
                (payload, hashlib.sha256(payload.encode()).hexdigest()),
            )
        return store

    @contextmanager
    def transaction(self):
        try:
            with (
                closing(
                    sqlite3.connect(self.path.resolve().as_uri() + "?mode=rw", uri=True, timeout=10)
                ) as db,
                db,
            ):
                db.execute("BEGIN IMMEDIATE")
                row = db.execute("SELECT payload,digest FROM state WHERE id=1").fetchone()
                if row is None:
                    raise PaperStateError("Missing paper state")
                if hashlib.sha256(row[0].encode()).hexdigest() != row[1]:
                    raise PaperStateError("Paper state digest mismatch")
                value = json.loads(row[0])
                if (
                    value.get("execution_available") is not False
                    or value.get("latched") is not True
                ):
                    raise PaperStateError("Unrecognized paper release state")
                if not 0 < amount(value["budget"]) <= 1000:
                    raise PaperStateError("Invalid stored budget")
                yield value
                payload = json.dumps(value, sort_keys=True)
                db.execute(
                    "UPDATE state SET payload=?,digest=? WHERE id=1",
                    (payload, hashlib.sha256(payload.encode()).hexdigest()),
                )
        except (sqlite3.Error, ValueError, KeyError, TypeError) as exc:
            raise PaperStateError("Paper state unavailable or invalid") from exc

    def read(self):
        with self.transaction() as state:
            return json.loads(json.dumps(state))

    def record_observation(self, observation, reasons):
        with self.transaction() as state:
            if observation.account_binding_sha256 != state["binding"]:
                raise PaperStateError("Paper account changed")
            state["observations"].append(
                {
                    "digest": observation.payload_sha256,
                    "received_at": observation.received_at.isoformat(),
                    "reasons": list(reasons),
                }
            )
            state["latch_reasons"] = sorted(set(state["latch_reasons"]) | set(reasons))

    def stage_intent(self, identifier, digest, cost):
        # Pending intent preparation only; cannot release a latch or submit an order.
        cost = amount(cost, positive=True)
        if not identifier or len(digest) != 64 or any(c not in "0123456789abcdef" for c in digest):
            raise PaperStateError("Invalid intent binding")
        with self.transaction() as state:
            existing = state["reservations"].get(identifier)
            row = {"digest": digest, "cost": str(cost), "submitted": False}
            if existing:
                if existing != row:
                    raise PaperStateError("Intent replay mismatch")
                return
            total = sum((amount(x["cost"]) for x in state["reservations"].values()), Decimal(0))
            if total + cost > amount(state["budget"]):
                raise PaperStateError("Paper budget exhausted")
            state["reservations"][identifier] = row

    def latch(self, reason):
        if not reason:
            raise PaperStateError("Reason required")
        with self.transaction() as state:
            state["latch_reasons"] = sorted(set(state["latch_reasons"]) | {reason})
