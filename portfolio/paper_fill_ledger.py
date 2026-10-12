"""Durable paper trade-cash/share ledger, never settled cash or execution authority."""

import hashlib
import json
from datetime import datetime
from decimal import Decimal

from portfolio.paper_fill_reconciliation import PaperFill
from risk.paper_state import PaperState, PaperStateError


class PaperFillLedger:
    def __init__(self, path):
        self.store = PaperState(path)

    @classmethod
    def initialize(cls, path, observation):
        if not (
            observation.bracket_stable
            and observation.account_unblocked
            and observation.empty_inventory
            and observation.equity == 1000
            and observation.cash == 1000
        ):
            raise PaperStateError("Verified empty $1,000 paper baseline required")
        store = PaperState.initialize(path, account_binding=observation.account_binding_sha256)
        with store.transaction() as state:
            state["fill_ledger"] = {
                "baseline_at": observation.received_at.isoformat(),
                "acquisition_cutoff": observation.received_at.isoformat(),
                "opening_cash": "1000",
                "trade_cash": "1000",
                "positions": {},
                "activities": {},
                "baseline_digest": observation.payload_sha256,
                "settlement_verified": False,
                "fees_flows_reconciled": False,
            }
        return cls(path)

    def read(self):
        state = self.store.read()
        if "fill_ledger" not in state:
            raise PaperStateError("Missing initialized fill ledger")
        return state["fill_ledger"]

    def import_batch(self, batch, *, account_binding):
        if not batch.pagination_exhausted:
            raise PaperStateError("Incomplete activity pagination")
        with self.store.transaction() as state:
            if state["binding"] != account_binding or "fill_ledger" not in state:
                raise PaperStateError("Account or ledger binding mismatch")
            ledger = state["fill_ledger"]
            baseline = datetime.fromisoformat(ledger["baseline_at"])
            cutoff = datetime.fromisoformat(ledger["acquisition_cutoff"])
            if batch.after > cutoff or batch.until < cutoff or batch.received_at < batch.until:
                raise PaperStateError("Activity coverage gap or regression")
            added = 0
            for row in batch.rows:
                canonical = json.dumps(row, sort_keys=True, separators=(",", ":"))
                digest = hashlib.sha256(canonical.encode()).hexdigest()
                identifier = row.get("id")
                if not isinstance(identifier, str) or not identifier:
                    raise PaperStateError("Missing activity identity")
                old = ledger["activities"].get(identifier)
                if old:
                    if old["digest"] != digest:
                        raise PaperStateError("Activity correction requires human reconciliation")
                    continue
                if row.get("activity_type") != "FILL":
                    # Retain unknown activities without treating them as cash effects.
                    state["latch_reasons"] = sorted(
                        set(state["latch_reasons"]) | {"UNMAPPED_ACCOUNT_ACTIVITY"}
                    )
                else:
                    fill = PaperFill.model_validate(row)
                    if (
                        not baseline < fill.transaction_time <= batch.until
                        or fill.transaction_time <= batch.after
                    ):
                        raise PaperStateError("Fill outside baseline/acquisition interval")
                ledger["activities"][identifier] = {"digest": digest, "row": row}
                added += 1
            # Rebuild from immutable baseline: overlapping pages cannot compound effects.
            fills = [
                PaperFill.model_validate(x["row"])
                for x in ledger["activities"].values()
                if x["row"].get("activity_type") == "FILL"
            ]
            fills.sort(key=lambda f: (f.transaction_time, f.order_id, f.cum_qty))
            cash, positions, orders = Decimal(ledger["opening_cash"]), {}, {}
            for fill in fills:
                previous = orders.get(fill.order_id)
                cumulative = (previous[2] if previous else Decimal(0)) + fill.qty
                if previous and previous[:2] != (fill.symbol, fill.side):
                    raise PaperStateError("Order identity changed")
                if cumulative != fill.cum_qty:
                    raise PaperStateError("Missing or conflicting cumulative fill history")
                orders[fill.order_id] = (fill.symbol, fill.side, cumulative)
                sign = Decimal(1) if fill.side == "buy" else Decimal(-1)
                cash -= sign * fill.qty * fill.price
                positions[fill.symbol] = positions.get(fill.symbol, Decimal(0)) + sign * fill.qty
                if cash < 0 or positions[fill.symbol] < 0:
                    raise PaperStateError("Unexplained borrowing or short position")
            ledger["trade_cash"] = str(cash)
            ledger["positions"] = {k: str(v) for k, v in positions.items() if v}
            ledger["acquisition_cutoff"] = batch.until.isoformat()
            state["latch_reasons"] = sorted(
                set(state["latch_reasons"])
                | {"FEES_AND_EXTERNAL_FLOWS_UNRECONCILED", "SETTLED_CASH_UNVERIFIED"}
            )
            return {
                "new_activities": added,
                "total_fills": len(fills),
                "execution_available": False,
                "settlement_verified": False,
            }
