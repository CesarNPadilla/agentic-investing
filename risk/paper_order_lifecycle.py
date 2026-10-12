"""Persist-before-send paper protocol fixtures; no production or real mutation gate."""

import hashlib
from decimal import Decimal

import httpx

from risk.paper_state import PaperStateError


class PaperOrderLifecycle:
    def __init__(self, store, protocol):
        self.store, self.protocol = store, protocol

    def submit_fixture_once(self, intent):
        if not isinstance(self.protocol._transport, httpx.MockTransport):
            raise PaperStateError("Real submission gate is unavailable")
        digest = hashlib.sha256(intent.model_dump_json().encode()).hexdigest()
        identifier = str(intent.client_order_id)
        cost = intent.quantity * intent.limit_price
        with self.store.transaction() as state:
            if state["binding"] != intent.account_binding:
                raise PaperStateError("Order account binding mismatch")
            orders = state.setdefault("paper_protocol_orders", {})
            previous = orders.get(identifier)
            if previous and previous["digest"] != digest:
                raise PaperStateError("Client order ID reuse mismatch")
            first = previous is None
            if first:
                total = sum(
                    (Decimal(x["cost"]) for x in state["reservations"].values()), Decimal(0)
                )
                resource_cost = cost if intent.side == "buy" else Decimal(0)
                if intent.side == "sell":
                    ledger = state.get("fill_ledger")
                    if not ledger:
                        raise PaperStateError("Sell requires durable holdings ledger")
                    holdings = Decimal(ledger["positions"].get(intent.symbol, "0"))
                    pledged = sum(
                        (
                            Decimal(r.get("held_quantity", "0"))
                            for r in state["reservations"].values()
                            if r.get("side") == "sell" and r.get("symbol") == intent.symbol
                        ),
                        Decimal(0),
                    )
                    if intent.quantity > holdings - pledged:
                        raise PaperStateError("Sell exceeds unreserved holdings")
                if total + resource_cost > Decimal(state["budget"]):
                    raise PaperStateError("Reservation capacity exceeded")
                if identifier in state["reservations"]:
                    raise PaperStateError("Existing unrelated reservation")
                state["reservations"][identifier] = {
                    "digest": digest,
                    "cost": str(resource_cost),
                    "side": intent.side,
                    "symbol": intent.symbol,
                    "held_quantity": str(intent.quantity if intent.side == "sell" else 0),
                    "submitted": False,
                }
                orders[identifier] = {"digest": digest, "phase": "SUBMISSION_UNCERTAIN"}
        # Transaction committed before the first POST. Replays use lookup only, even on 404.
        try:
            receipt = (
                self.protocol.submit_fixture(intent) if first else self.protocol.lookup(intent)
            )
            if receipt is None:
                return {"phase": "SUBMISSION_UNCERTAIN", "execution_available": False}
            with self.store.transaction() as state:
                previous = state["paper_protocol_orders"][identifier]
                if Decimal(receipt["filled_quantity"]) < Decimal(
                    previous.get("filled_quantity", "0")
                ):
                    raise PaperStateError("Fill quantity regressed")
                if (
                    previous["phase"] in {"filled", "canceled", "expired", "rejected"}
                    and receipt["status"] != previous["phase"]
                ):
                    raise PaperStateError("Terminal order state changed")
                if previous.get("broker_order_id") not in (None, receipt["broker_order_id"]):
                    raise PaperStateError("Broker order identity changed")
                state["paper_protocol_orders"][identifier]["broker_order_id"] = receipt[
                    "broker_order_id"
                ]
                state["paper_protocol_orders"][identifier]["phase"] = receipt["status"]
                state["paper_protocol_orders"][identifier]["filled_quantity"] = receipt[
                    "filled_quantity"
                ]
            return receipt
        except (httpx.HTTPError, ValueError, TypeError, ArithmeticError, PaperStateError):
            self.store.latch("PAPER_ORDER_RESPONSE_UNCERTAIN")
            return {"phase": "SUBMISSION_UNCERTAIN", "execution_available": False}

    def reconcile_reservation(self, intent):
        # Terminal receipt alone is insufficient: exact fills must exist in bound durable ledger.
        identifier = str(intent.client_order_id)
        digest = hashlib.sha256(intent.model_dump_json().encode()).hexdigest()
        with self.store.transaction() as state:
            if state["binding"] != intent.account_binding or "fill_ledger" not in state:
                raise PaperStateError("Missing account-bound fill ledger")
            order = state.get("paper_protocol_orders", {}).get(identifier)
            reservation = state["reservations"].get(identifier)
            if not order or not reservation or order["digest"] != digest:
                raise PaperStateError("Missing bound reservation/order")
            broker_id = order.get("broker_order_id")
            if not broker_id:
                raise PaperStateError("Broker order identity unresolved")
            from portfolio.paper_fill_reconciliation import PaperFill

            fills = [
                PaperFill.model_validate(x["row"])
                for x in state["fill_ledger"]["activities"].values()
                if x["row"].get("activity_type") == "FILL" and x["row"].get("order_id") == broker_id
            ]
            quantity = sum((f.qty for f in fills), Decimal(0))
            if quantity != Decimal(order.get("filled_quantity", "0")):
                raise PaperStateError("Receipt and durable fill quantities differ")
            if any(
                f.symbol != intent.symbol
                or f.side != intent.side
                or (
                    f.price > intent.limit_price
                    if intent.side == "buy"
                    else f.price < intent.limit_price
                )
                for f in fills
            ):
                raise PaperStateError("Fill identity/price differs from reservation")
            consumed = sum((f.qty * f.price for f in fills), Decimal(0))
            if quantity > intent.quantity or (
                intent.side == "buy" and consumed > intent.quantity * intent.limit_price
            ):
                raise PaperStateError("Fill exceeds intent")
            terminal = order["phase"] in {"filled", "canceled", "expired", "rejected"}
            pending = Decimal(0) if terminal else (intent.quantity - quantity) * intent.limit_price
            # Filled cost stays consumed. No sale/cash replenishment or fee assumption follows.
            if intent.side == "buy":
                reservation.update(
                    cost=str(consumed + pending),
                    consumed=str(consumed),
                    pending=str(pending),
                    submitted=True,
                    terminal_reconciled=terminal,
                )
            else:
                reservation.update(
                    cost="0",
                    held_quantity=str(0 if terminal else intent.quantity - quantity),
                    sale_proceeds_unsettled=str(consumed),
                    submitted=True,
                    terminal_reconciled=terminal,
                )
            return {
                "consumed": str(consumed),
                "pending": str(pending),
                "terminal_reconciled": terminal,
                "execution_available": False,
                "fees_reconciled": False,
            }

    def reconcile_buy_reservation(self, intent):
        if intent.side != "buy":
            raise PaperStateError("Buy reconciliation requires buy intent")
        return self.reconcile_reservation(intent)
