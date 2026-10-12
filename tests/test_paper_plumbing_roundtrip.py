from datetime import date

from strategies.paper_plumbing_roundtrip import next_intent


def intent(**changes):
    args = {
        "binding": "a" * 64,
        "day": date(2026, 10, 5),
        "last_entry_day": None,
        "owned_quantity": 0,
        "observed_quantity": 0,
        "entry_terminal": False,
        "has_open_order": False,
        "regular_session": True,
        "trial_ended": False,
        "reconciliation_verified": True,
        "bid": 30,
        "ask": 31,
        "account_equity": 1000,
        "sleeve_equity": 1000,
        "settled_cash": 1000,
    }
    args.update(changes)
    return next_intent(**args)


def test_roundtrip_and_daily_reentry():
    buy = intent()
    assert buy["action"] == "BUY_INTENT_ONLY"
    assert buy["client_order_id"] == intent()["client_order_id"]
    sell = intent(
        owned_quantity=1, observed_quantity=1, entry_terminal=True, last_entry_day=date(2026, 10, 5)
    )
    assert sell["action"] == "SELL_INTENT_ONLY"
    assert sell["client_order_id"] != buy["client_order_id"]
    assert intent(last_entry_day=date(2026, 10, 5))["action"] == "HOLD"
    assert (
        intent(day=date(2026, 10, 6), last_entry_day=date(2026, 10, 5))["client_order_id"]
        != buy["client_order_id"]
    )
    assert not sell["execution_available"]


def test_foreign_and_unreconciled_holdings_never_exit():
    assert intent(observed_quantity=2)["action"] == "HOLD"
    assert intent(owned_quantity=2, observed_quantity=1)["action"] == "HOLD"
    assert intent(owned_quantity=1, observed_quantity=1)["action"] == "HOLD"
    sell = intent(
        owned_quantity=1, observed_quantity=2, entry_terminal=True, last_entry_day=date(2026, 10, 5)
    )
    assert sell["quantity"] == 1


def test_session_pending_end_and_minimum_are_blocked():
    for changes in (
        {"has_open_order": True},
        {"regular_session": False},
        {"trial_ended": True},
        {"reconciliation_verified": False},
        {"settled_cash": 10},
        {"binding": "invalid"},
        {"last_entry_day": date(2026, 10, 6)},
    ):
        assert intent(**changes)["action"] == "HOLD"
    assert (
        intent(
            owned_quantity=1,
            observed_quantity=1,
            entry_terminal=True,
            last_entry_day=date(2026, 10, 5),
            bid=24,
        )["action"]
        == "HOLD"
    )
