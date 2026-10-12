import json
from datetime import date
from uuid import NAMESPACE_URL, uuid5

import httpx
import pytest

from integrations.brokers.alpaca_paper_orders import PaperOrderProtocol
from risk.paper_state import PaperState, PaperStateError
from workers.paper_plumbing_fixture import PlumbingFixtureRunner


def observations(**changes):
    values = {
        "day": date(2026, 10, 5),
        "observed_quantity": 0,
        "bid": 30,
        "ask": 31,
        "account_equity": 1000,
        "sleeve_equity": 1000,
        "settled_cash": 1000,
        "regular_session": True,
        "trial_ended": False,
        "reconciliation_verified": True,
    }
    values.update(changes)
    return values


def test_roundtrip_claim_order_fill_reservations_and_restart(tmp_path):
    store = PaperState.initialize(tmp_path / "paper.sqlite", account_binding="a" * 64)
    with store.transaction() as state:
        state["fill_ledger"] = {"positions": {}, "activities": {}}
    receipts, methods = {}, []

    def handler(request):
        methods.append(request.method)
        if request.method == "POST":
            row = json.loads(request.content)
            identifier = row["client_order_id"]
            receipts[identifier] = dict(
                row,
                id=str(uuid5(NAMESPACE_URL, identifier)),
                status="filled",
                filled_qty=row["qty"],
            )
        else:
            identifier = request.url.params["client_order_id"]
        return httpx.Response(200, json=receipts[identifier])

    protocol = PaperOrderProtocol(
        "fixture-key", "fixture-secret", transport=httpx.MockTransport(handler)
    )
    runner = PlumbingFixtureRunner(store, protocol)
    buy = runner.prepare_fixture(**observations())
    runner.recover_fixture(buy["client_order_id"])
    with pytest.raises(PaperStateError):
        runner.prepare_fixture(**observations(observed_quantity=1))

    def add_fill(intent, side):
        broker = receipts[intent["client_order_id"]]["id"]
        with store.transaction() as state:
            state["fill_ledger"]["positions"] = {"INTC": "1"} if side == "buy" else {}
            state["fill_ledger"]["activities"][broker] = {
                "row": {
                    "activity_type": "FILL",
                    "id": broker,
                    "order_id": broker,
                    "symbol": "INTC",
                    "side": side,
                    "qty": "1",
                    "price": "30",
                    "cum_qty": "1",
                    "leaves_qty": "0",
                    "transaction_time": "2026-10-05T15:00:00Z",
                }
            }

    add_fill(buy, "buy")
    runner = PlumbingFixtureRunner(PaperState(store.path), protocol)
    runner.recover_fixture(buy["client_order_id"])
    sell = runner.prepare_fixture(**observations(observed_quantity=1))
    assert sell["action"] == "SELL_INTENT_ONLY"
    runner.recover_fixture(sell["client_order_id"])
    add_fill(sell, "sell")
    assert runner.prepare_fixture(**observations())["reason"] == "DAILY_ROUNDTRIP_COMPLETE"
    assert methods == ["POST", "GET", "POST"]
    reservations = store.read()["reservations"]
    assert reservations[buy["client_order_id"]]["consumed"] == "30"
    assert reservations[sell["client_order_id"]]["held_quantity"] == "0"
    assert reservations[sell["client_order_id"]]["sale_proceeds_unsettled"] == "30"


def test_real_transport_rejected_before_state_access():
    with pytest.raises(PaperStateError):
        PlumbingFixtureRunner(None, PaperOrderProtocol("key", "secret"))
