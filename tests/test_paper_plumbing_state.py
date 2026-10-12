from datetime import date

import pytest

from risk.paper_state import PaperState, PaperStateError
from strategies.paper_plumbing_state import prepare_intent


def prepare(store, **changes):
    args = {
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
    args.update(changes)
    return prepare_intent(store, **args)


def state(tmp_path):
    store = PaperState.initialize(tmp_path / "paper.sqlite", account_binding="a" * 64)
    with store.transaction() as value:
        value["fill_ledger"] = {"activities": {}}
    return store


def test_prepare_survives_restart_and_cannot_reprice_or_duplicate(tmp_path):
    store = state(tmp_path)
    first = prepare(store)
    assert first["action"] == "BUY_INTENT_ONLY"
    restarted = PaperState(store.path)
    assert prepare(restarted, ask=32)["reason"] == "PREPARED_INTENT_REQUIRES_RECOVERY"
    claims = restarted.read()["paper_plumbing_claims"]
    assert len(claims) == 1
    assert next(iter(claims.values()))["intent"]["limit_price"] == "31"


def test_foreign_holdings_never_become_strategy_owned(tmp_path):
    store = state(tmp_path)
    assert prepare(store, observed_quantity=2)["action"] == "HOLD"
    assert store.read()["paper_plumbing_claims"] == {}


def test_missing_fill_blocks_terminal_receipt(tmp_path):
    store = state(tmp_path)
    first = prepare(store)
    with store.transaction() as value:
        value["paper_protocol_orders"] = {
            first["client_order_id"]: {
                "broker_order_id": "broker",
                "phase": "filled",
                "filled_quantity": "1",
            }
        }
    with pytest.raises(PaperStateError):
        prepare(store, observed_quantity=1)


def test_owned_roundtrip_and_next_day_after_restart(tmp_path):
    store = state(tmp_path)
    buy = prepare(store)

    def fill(intent, side, broker):
        with store.transaction() as value:
            value.setdefault("paper_protocol_orders", {})[intent["client_order_id"]] = {
                "broker_order_id": broker,
                "phase": "filled",
                "filled_quantity": "1",
            }
            value["fill_ledger"]["activities"][broker] = {
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

    fill(buy, "buy", "entry")
    sell = prepare(PaperState(store.path), observed_quantity=1)
    assert sell["action"] == "SELL_INTENT_ONLY" and sell["quantity"] == 1
    fill(sell, "sell", "exit")
    assert prepare(PaperState(store.path))["reason"] == "DAILY_ROUNDTRIP_COMPLETE"
    next_day = prepare(PaperState(store.path), day=date(2026, 10, 6))
    assert next_day["action"] == "BUY_INTENT_ONLY"
    assert next_day["client_order_id"] != buy["client_order_id"]
