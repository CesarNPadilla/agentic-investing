"""Isolated synthetic cash/sleeve reservations; SQLite qualification only."""
import hashlib
import json
import sqlite3
from contextlib import closing, contextmanager
from decimal import Decimal
from pathlib import Path
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field

Amount = Annotated[Decimal, Field(gt=0, allow_inf_nan=False)]
Nonnegative = Annotated[Decimal, Field(ge=0, allow_inf_nan=False)]


class ReservationIntent(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    evidence_class: Literal["SYNTHETIC_ONLY"] = "SYNTHETIC_ONLY"
    proposal_id: str = Field(min_length=1)
    proposal_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    amount: Amount  # Conservative acquisition notional including fees.


class ReservationSnapshot(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    cash_available: Nonnegative
    sleeve_available: Nonnegative
    committed: Nonnegative
    execution_available: Literal[False] = False


class ReservationError(RuntimeError):
    """Reservation cannot be safely established or changed; callers must block."""


class SyntheticReservations:
    """One explicitly scoped synthetic ledger with fixed capacity.

    Partial fills transfer pending capacity to consumed capacity without freeing
    either resource. Only verified terminal evidence releases unfilled capacity.
    Filled acquisition costs stay consumed. No cash replenishment, live status
    trust, valuation/risk checks, broker integration or expiry release is implied.
    """
    def __init__(self, path: Path):
        self.path = Path(path)

    @classmethod
    def initialize(cls, path: Path, *, cash: Decimal, sleeve: Decimal):
        capacity = ReservationSnapshot(cash_available=cash, sleeve_available=sleeve, committed=0)
        store = cls(path)
        try:
            with closing(sqlite3.connect(path, timeout=10)) as db, db:
                db.execute("BEGIN IMMEDIATE")
                if db.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchone():
                    raise ReservationError("Refusing existing database")
                db.execute("CREATE TABLE events (seq INTEGER PRIMARY KEY, payload TEXT NOT NULL, "
                           "previous TEXT NOT NULL, digest TEXT NOT NULL)")
                store._append(db, {"kind": "BOOTSTRAP", "capacity": capacity.model_dump_json()})
        except sqlite3.Error as exc:
            raise ReservationError("Synthetic storage unavailable") from exc
        return store

    @contextmanager
    def _transaction(self):
        try:
            with closing(sqlite3.connect(self.path.resolve().as_uri() + "?mode=rw",
                                         uri=True, timeout=10)) as db, db:
                db.execute("BEGIN IMMEDIATE")
                tables = {r[0] for r in db.execute("SELECT name FROM sqlite_master WHERE type='table'")}
                if tables != {"events"}:
                    raise ReservationError("Not an isolated reservation database")
                yield db
        except (sqlite3.Error, ValueError, KeyError, TypeError) as exc:
            raise ReservationError("Synthetic reservation state unavailable or inconsistent") from exc

    @staticmethod
    def _append(db, event):
        last = db.execute("SELECT seq, digest FROM events ORDER BY seq DESC LIMIT 1").fetchone()
        seq, previous = (last[0] + 1, last[1]) if last else (1, "")
        payload = json.dumps(event, sort_keys=True)
        digest = hashlib.sha256((previous + "\n" + payload).encode()).hexdigest()
        db.execute("INSERT INTO events VALUES (?, ?, ?, ?)", (seq, payload, previous, digest))

    @staticmethod
    def _replay(db):
        rows = db.execute("SELECT seq, payload, previous, digest FROM events ORDER BY seq").fetchall()
        if not rows:
            raise ReservationError("Missing reservation state")
        previous, capacity, orders = "", None, {}
        for index, (seq, payload, prior, digest) in enumerate(rows, 1):
            if seq != index or prior != previous or digest != hashlib.sha256(
                    (prior + "\n" + payload).encode()).hexdigest():
                raise ReservationError("Reservation journal integrity failure")
            e = json.loads(payload)
            if index == 1:
                if e["kind"] != "BOOTSTRAP":
                    raise ReservationError("Missing bootstrap")
                capacity = ReservationSnapshot.model_validate_json(e["capacity"])
                if capacity.committed != 0:
                    raise ReservationError("Invalid initial commitments")
            elif e["kind"] == "RESERVE":
                intent = ReservationIntent.model_validate_json(e["intent"])
                if intent.proposal_id in orders:
                    raise ReservationError("Duplicate reservation event")
                orders[intent.proposal_id] = {"intent": intent, "filled": Decimal(0), "terminal": False}
            elif e["kind"] == "RECONCILE":
                order = orders[e["proposal_id"]]
                filled = Decimal(e["filled"])
                expected_terminal = (e["status"] in {"CANCELED", "REJECTED", "FILLED"}
                                     and e["synthetic_terminal_verified"])
                if (type(e["synthetic_terminal_verified"]) is not bool
                        or e["status"] not in {"OPEN", "PARTIAL", "PENDING_CANCEL", "UNKNOWN",
                                               "CANCELED", "REJECTED", "FILLED"}
                        or e["terminal"] != expected_terminal):
                    raise ReservationError("Unverified terminal release")
                if (not filled.is_finite() or order["terminal"] or filled < order["filled"]
                        or filled > order["intent"].amount or type(e["terminal"]) is not bool):
                    raise ReservationError("Invalid reconciliation sequence")
                order.update(filled=filled, terminal=e["terminal"])
            else:
                raise ReservationError("Unknown event")
            used = sum((o["filled"] if o["terminal"] else o["intent"].amount
                        for o in orders.values()), Decimal(0))
            if used > min(capacity.cash_available, capacity.sleeve_available):
                raise ReservationError("Persisted capacity exceeded")
            previous = digest
        return capacity, orders, used

    @staticmethod
    def _snapshot(capacity, used):
        return ReservationSnapshot(cash_available=capacity.cash_available-used,
                                   sleeve_available=capacity.sleeve_available-used, committed=used)

    def snapshot(self):
        with self._transaction() as db:
            capacity, _, used = self._replay(db)
            return self._snapshot(capacity, used)

    def reserve(self, intent: ReservationIntent):
        with self._transaction() as db:
            capacity, orders, used = self._replay(db)
            existing = orders.get(intent.proposal_id)
            if existing:
                if existing["intent"] != intent:
                    raise ReservationError("Proposal ID reused with changed digest or amount")
                if existing["terminal"]:
                    raise ReservationError("Terminal proposal requires a new identity")
                return self._snapshot(capacity, used)
            if used + intent.amount > min(capacity.cash_available, capacity.sleeve_available):
                raise ReservationError("Insufficient cash or sleeve capacity")
            self._append(db, {"kind": "RESERVE", "intent": intent.model_dump_json()})
            return self._snapshot(capacity, used + intent.amount)

    def reconcile(self, proposal_id: str, *, cumulative_filled: Decimal,
                  status: Literal["OPEN", "PARTIAL", "PENDING_CANCEL", "UNKNOWN",
                                  "CANCELED", "REJECTED", "FILLED"],
                  synthetic_terminal_verified: bool = False):
        if status not in {"OPEN", "PARTIAL", "PENDING_CANCEL", "UNKNOWN", "CANCELED", "REJECTED", "FILLED"}:
            raise ReservationError("Unknown status")
        if type(synthetic_terminal_verified) is not bool:
            raise ReservationError("Verification must be boolean")
        with self._transaction() as db:
            filled = Decimal(cumulative_filled)
            capacity, orders, used = self._replay(db)
            order = orders.get(proposal_id)
            if not order or not filled.is_finite() or filled < order["filled"] or filled > order["intent"].amount:
                raise ReservationError("Unknown proposal or invalid cumulative fill")
            terminal = status in {"CANCELED", "REJECTED", "FILLED"} and synthetic_terminal_verified
            if order["terminal"]:
                if terminal and filled == order["filled"]:
                    return self._snapshot(capacity, used)
                raise ReservationError("Terminal state cannot reopen or change")
            self._append(db, {"kind": "RECONCILE", "proposal_id": proposal_id,
                              "filled": str(filled), "terminal": terminal, "status": status,
                              "synthetic_terminal_verified": synthetic_terminal_verified})
            released = order["intent"].amount - filled if terminal else Decimal(0)
            return self._snapshot(capacity, used-released)
