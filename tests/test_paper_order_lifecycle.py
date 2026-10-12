from concurrent.futures import ThreadPoolExecutor
from uuid import NAMESPACE_URL, uuid4, uuid5

import httpx
import pytest

from integrations.brokers.alpaca_paper_orders import PaperOrderIntent, PaperOrderProtocol
from risk.paper_order_lifecycle import PaperOrderLifecycle
from risk.paper_state import PaperState, PaperStateError

BIND = "a" * 64


def intent():
    return PaperOrderIntent(
        client_order_id=uuid4(), account_binding=BIND, side="buy", quantity=1, limit_price=30
    )


def receipt(x, status="accepted", qty="0"):
    return dict(
        x.request(),
        id=str(uuid5(NAMESPACE_URL, str(x.client_order_id))),
        status=status,
        filled_qty=qty,
    )


def setup(tmp_path, handler):
    store = PaperState.initialize(tmp_path / "state.sqlite", account_binding=BIND)
    protocol = PaperOrderProtocol("test-key", "test-secret", transport=httpx.MockTransport(handler))
    return store, protocol, PaperOrderLifecycle(store, protocol)


def test_persisted_claim_precedes_post_and_replays_get_only(tmp_path):
    x = intent()
    methods = []

    def handler(request):
        methods.append(request.method)
        assert request.url.host == "paper-api.alpaca.markets"
        assert store.read()["paper_protocol_orders"][str(x.client_order_id)]["phase"] in {
            "SUBMISSION_UNCERTAIN",
            "accepted",
        }
        return httpx.Response(200, json=receipt(x))

    store, protocol, lifecycle = setup(tmp_path, handler)
    assert lifecycle.submit_fixture_once(x)["status"] == "accepted"
    assert (
        PaperOrderLifecycle(PaperState(store.path), protocol).submit_fixture_once(x)["status"]
        == "accepted"
    )
    assert methods == ["POST", "GET"]


def test_timeout_and_404_never_resubmit_or_free_reservation(tmp_path):
    x = intent()
    methods = []

    def handler(request):
        methods.append(request.method)
        if request.method == "POST":
            raise httpx.ReadTimeout("private-response")
        return httpx.Response(404)

    store, _, lifecycle = setup(tmp_path, handler)
    assert lifecycle.submit_fixture_once(x)["phase"] == "SUBMISSION_UNCERTAIN"
    assert lifecycle.submit_fixture_once(x)["phase"] == "SUBMISSION_UNCERTAIN"
    assert methods == ["POST", "GET"] and len(store.read()["reservations"]) == 1
    assert "PAPER_ORDER_RESPONSE_UNCERTAIN" in store.read()["latch_reasons"]


def test_crash_after_claim_concurrent_replay_and_changed_id(tmp_path):
    x = intent()
    methods = []

    def handler(request):
        methods.append(request.method)
        return httpx.Response(200, json=receipt(x))

    store, _, lifecycle = setup(tmp_path, handler)
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(lambda _: lifecycle.submit_fixture_once(x), [1, 2]))
    assert len(results) == 2
    assert methods.count("POST") == 1
    with pytest.raises(PaperStateError):
        lifecycle.submit_fixture_once(x.model_copy(update={"quantity": 2}))
    assert len(store.read()["reservations"]) == 1


def test_partial_fill_regression_and_wrong_broker_symbol_block(tmp_path):
    x = PaperOrderIntent(
        client_order_id=uuid4(), account_binding=BIND, side="buy", quantity=2, limit_price=30
    )
    count = 0

    def handler(request):
        nonlocal count
        count += 1
        return httpx.Response(200, json=receipt(x, "partially_filled", "1" if count == 1 else "0"))

    store, _, lifecycle = setup(tmp_path, handler)
    lifecycle.submit_fixture_once(x)
    assert lifecycle.submit_fixture_once(x)["phase"] == "SUBMISSION_UNCERTAIN"
    assert store.read()["paper_protocol_orders"][str(x.client_order_id)]["filled_quantity"] == "1"
    assert len(store.read()["reservations"]) == 1


def test_real_transport_cannot_submit_and_lookup_mismatch_rejected():
    x = intent()
    with pytest.raises(PaperStateError):
        PaperOrderProtocol("k", "s").submit_fixture(x)
    wrong = receipt(x)
    wrong["symbol"] = "AAPL"
    with pytest.raises(PaperStateError):
        PaperOrderProtocol.validate(httpx.Response(200, json=wrong), x)


def test_process_interruption_after_claim_recovers_by_lookup_only(tmp_path):
    x = intent()
    methods = []

    def handler(request):
        methods.append(request.method)
        if request.method == "POST":
            raise KeyboardInterrupt()
        return httpx.Response(200, json=receipt(x))

    store, protocol, lifecycle = setup(tmp_path, handler)
    with pytest.raises(KeyboardInterrupt):
        lifecycle.submit_fixture_once(x)
    assert (
        store.read()["paper_protocol_orders"][str(x.client_order_id)]["phase"]
        == "SUBMISSION_UNCERTAIN"
    )
    PaperOrderLifecycle(PaperState(store.path), protocol).submit_fixture_once(x)
    assert methods == ["POST", "GET"]


def test_cancel_ack_is_not_terminal_evidence_or_reservation_release(tmp_path):
    x = intent()
    broker_id = str(uuid4())
    methods = []

    def handler(request):
        methods.append(request.method)
        if request.method == "DELETE":
            assert request.url.path.endswith(broker_id)
            return httpx.Response(204)
        return httpx.Response(200, json=dict(receipt(x), id=broker_id))

    store, protocol, lifecycle = setup(tmp_path, handler)
    lifecycle.submit_fixture_once(x)
    assert protocol.cancel_fixture(x)["phase"] == "CANCEL_UNCERTAIN"
    assert methods == ["POST", "GET", "DELETE"]
    assert len(store.read()["reservations"]) == 1


def test_partial_cancel_releases_only_unfilled_cost_with_durable_fill_match(tmp_path):
    x = PaperOrderIntent(
        client_order_id=uuid4(), account_binding=BIND, side="buy", quantity=2, limit_price=30
    )
    stage = {"status": "partially_filled"}

    def handler(request):
        return httpx.Response(200, json=receipt(x, stage["status"], "1"))

    store, _, lifecycle = setup(tmp_path, handler)
    lifecycle.submit_fixture_once(x)
    broker_id = receipt(x)["id"]
    with store.transaction() as state:
        state["fill_ledger"] = {
            "activities": {
                "f": {
                    "row": {
                        "activity_type": "FILL",
                        "id": "f",
                        "order_id": broker_id,
                        "symbol": "INTC",
                        "side": "buy",
                        "qty": "1",
                        "price": "29",
                        "cum_qty": "1",
                        "leaves_qty": "1",
                        "transaction_time": "2026-10-05T15:00:00Z",
                    }
                }
            }
        }
    result = lifecycle.reconcile_buy_reservation(x)
    assert result["consumed"] == "29" and result["pending"] == "30"
    assert store.read()["reservations"][str(x.client_order_id)]["cost"] == "59"
    stage["status"] = "canceled"
    lifecycle.submit_fixture_once(x)
    result = lifecycle.reconcile_buy_reservation(x)
    assert result["terminal_reconciled"] and result["pending"] == "0"
    assert store.read()["reservations"][str(x.client_order_id)]["cost"] == "29"
    assert lifecycle.reconcile_buy_reservation(x) == result


def test_terminal_receipt_without_exact_durable_fill_match_never_releases(tmp_path):
    x = intent()
    store, _, lifecycle = setup(
        tmp_path, lambda request: httpx.Response(200, json=receipt(x, "filled", "1"))
    )
    lifecycle.submit_fixture_once(x)
    with store.transaction() as state:
        state["fill_ledger"] = {"activities": {}}
    with pytest.raises(PaperStateError):
        lifecycle.reconcile_buy_reservation(x)
    assert store.read()["reservations"][str(x.client_order_id)]["cost"] == "30"


def test_sell_holds_shares_and_never_releases_proceeds_as_cash(tmp_path):
    x = PaperOrderIntent(
        client_order_id=uuid4(), account_binding=BIND, side="sell", quantity=2, limit_price=30
    )
    store, _, lifecycle = setup(
        tmp_path, lambda request: httpx.Response(200, json=receipt(x, "partially_filled", "1"))
    )
    with store.transaction() as state:
        state["fill_ledger"] = {"positions": {"INTC": "2"}, "activities": {}}
    lifecycle.submit_fixture_once(x)
    competing = x.model_copy(update={"client_order_id": uuid4()})
    with pytest.raises(PaperStateError):
        lifecycle.submit_fixture_once(competing)
    broker_id = receipt(x)["id"]
    with store.transaction() as state:
        state["fill_ledger"]["positions"] = {"INTC": "1"}
        state["fill_ledger"]["activities"] = {
            "f": {
                "row": {
                    "activity_type": "FILL",
                    "id": "f",
                    "order_id": broker_id,
                    "symbol": "INTC",
                    "side": "sell",
                    "qty": "1",
                    "price": "31",
                    "cum_qty": "1",
                    "leaves_qty": "1",
                    "transaction_time": "2026-10-05T15:00:00Z",
                }
            }
        }
    lifecycle.reconcile_reservation(x)
    row = store.read()["reservations"][str(x.client_order_id)]
    assert (
        row["cost"] == "0"
        and row["held_quantity"] == "1"
        and row["sale_proceeds_unsettled"] == "31"
    )
