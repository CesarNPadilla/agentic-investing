"""Durable paper intent preparation; no submission or admission authority."""

from datetime import date
from decimal import Decimal

from portfolio.paper_fill_reconciliation import PaperFill
from risk.paper_state import PaperStateError
from strategies.paper_etf_plumbing import VERSION, next_intent

TERMINAL = {"filled", "canceled", "expired", "rejected"}


def prepare_intent(
    store,
    *,
    day,
    observed_quantity,
    bid,
    ask,
    account_equity,
    sleeve_equity,
    settled_cash,
    regular_session,
    trial_ended,
    reconciliation_verified,
):
    """Persist an immutable intent in the same transaction as its daily claim.

    Only fills matching broker IDs of this strategy's durable claims count as
    owned. Missing order receipts or mismatched quantities block preparation.
    Replayed prepared intents retain their original price and identifier.
    """
    with store.transaction() as state:
        claims = state.setdefault("paper_etf_plumbing_claims", {})
        ledger = state.get("fill_ledger")
        if ledger is None:
            raise PaperStateError("Durable fill ledger required")
        if any(c["version"] != VERSION for c in claims.values()):
            raise PaperStateError("Strategy version changed")
        if any(
            c["intent"].get("symbol") != "SCHB"
            or c["intent"].get("strategy_id") != "PAPER_ETF_CONTROL_PLUMBING"
            for c in claims.values()
        ):
            raise PaperStateError("ETF claim identity changed")
        buys = [c for c in claims.values() if c["intent"]["action"] == "BUY_INTENT_ONLY"]
        last_day = max((date.fromisoformat(c["day"]) for c in buys), default=None)
        orders = state.get("paper_protocol_orders", {})
        owned, entry_terminal = Decimal(0), False
        unresolved = False
        prepared = []
        broker_ids = set()
        for identifier, claim in claims.items():
            order = orders.get(identifier)
            if order is None:
                prepared.append(claim)
                continue
            broker_id = order.get("broker_order_id")
            if not broker_id or broker_id in broker_ids:
                unresolved = True
                continue
            broker_ids.add(broker_id)
            fills = [
                PaperFill.model_validate(x["row"])
                for x in ledger["activities"].values()
                if x["row"].get("activity_type") == "FILL" and x["row"].get("order_id") == broker_id
            ]
            side = "buy" if claim["intent"]["action"] == "BUY_INTENT_ONLY" else "sell"
            qty = sum((f.qty for f in fills), Decimal(0))
            if (
                any(f.symbol != "SCHB" or f.side != side for f in fills)
                or qty != Decimal(order.get("filled_quantity", "0"))
                or qty > claim["intent"]["quantity"]
            ):
                raise PaperStateError("Strategy fills disagree with order receipt")
            owned += qty if side == "buy" else -qty
            unresolved |= order["phase"] not in TERMINAL
            if side == "buy" and date.fromisoformat(claim["day"]) == last_day:
                entry_terminal = order["phase"] in TERMINAL
        if owned < 0:
            raise PaperStateError("Strategy ownership became negative")
        if prepared:
            # Restart recovery exposes only the original claim; it never makes a second claim.
            return {
                "action": "HOLD",
                "reason": "PREPARED_INTENT_REQUIRES_RECOVERY",
                "prepared_client_order_ids": sorted(
                    c["intent"]["client_order_id"] for c in prepared
                ),
                "execution_available": False,
            }
        result = next_intent(
            binding=state["binding"],
            day=day,
            last_entry_day=last_day,
            owned_quantity=owned,
            observed_quantity=observed_quantity,
            entry_terminal=entry_terminal,
            has_open_order=unresolved,
            regular_session=regular_session,
            trial_ended=trial_ended,
            reconciliation_verified=reconciliation_verified,
            bid=bid,
            ask=ask,
            account_equity=account_equity,
            sleeve_equity=sleeve_equity,
            settled_cash=settled_cash,
        )
        if result["action"] != "HOLD":
            identifier = result["client_order_id"]
            if identifier in claims:
                return {
                    "action": "HOLD",
                    "reason": "CLAIM_ALREADY_USED_REVIEW_REQUIRED",
                    "execution_available": False,
                }
            claims[identifier] = {"version": VERSION, "day": day.isoformat(), "intent": result}
        return result
