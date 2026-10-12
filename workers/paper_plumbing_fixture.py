"""Integrated plumbing qualification harness; mock broker transport required."""

import httpx

from integrations.brokers.alpaca_paper_orders import PaperOrderIntent
from risk.paper_order_lifecycle import PaperOrderLifecycle
from risk.paper_state import PaperStateError
from strategies.paper_plumbing_state import prepare_intent


class PlumbingFixtureRunner:
    def __init__(self, store, protocol):
        if not isinstance(protocol._transport, httpx.MockTransport):
            raise PaperStateError("Plumbing qualification requires mock transport")
        self.store = store
        self.lifecycle = PaperOrderLifecycle(store, protocol)

    def _intent(self, identifier):
        state = self.store.read()
        claim = state.get("paper_plumbing_claims", {}).get(identifier)
        if claim is None:
            raise PaperStateError("Missing durable plumbing claim")
        row = claim["intent"]
        return PaperOrderIntent(
            client_order_id=row["client_order_id"],
            account_binding=state["binding"],
            symbol=row["symbol"],
            side="buy" if row["action"] == "BUY_INTENT_ONLY" else "sell",
            quantity=row["quantity"],
            limit_price=row["limit_price"],
        )

    def recover_fixture(self, identifier):
        # First call sends only an already-persisted claim; later calls lookup only.
        return self.lifecycle.submit_fixture_once(self._intent(identifier))

    def prepare_fixture(self, **observations):
        state = self.store.read()
        for identifier in state.get("paper_plumbing_claims", {}):
            if identifier in state.get("paper_protocol_orders", {}):
                self.lifecycle.reconcile_reservation(self._intent(identifier))
        return prepare_intent(self.store, **observations)
