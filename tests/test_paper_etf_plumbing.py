from datetime import date
from decimal import Decimal
from uuid import UUID

import httpx
import pytest
from pydantic import ValidationError

from integrations.brokers.alpaca_paper_etf_orders import PaperETFOrderIntent
from integrations.brokers.alpaca_paper_orders import PaperOrderProtocol
from risk.paper_state import PaperStateError
from strategies.paper_etf_plumbing import next_intent
from strategies.paper_plumbing_roundtrip import next_intent as historical_intent


def args(**changes):
    result = {
        "binding": "a" * 64,
        "day": date(2026, 10, 6),
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
    result.update(changes)
    return result


def test_etf_identity_is_distinct_stable_and_never_authorizes_execution():
    result = next_intent(**args())
    assert result["symbol"] == "SCHB"
    assert result["client_order_id"] == next_intent(**args())["client_order_id"]
    assert result["client_order_id"] != historical_intent(**args())["client_order_id"]
    assert not result["execution_available"]


@pytest.mark.parametrize(
    "changes",
    [
        {"ask": 0},
        {"ask": "NaN"},
        {"ask": 101},
        {"ask": 31, "account_equity": 300},
        {"settled_cash": 24},
        {"ask": 31, "sleeve_equity": 100},
        {"regular_session": False},
        {"has_open_order": True},
        {"trial_ended": True},
        {"observed_quantity": 1},
    ],
)
def test_invalid_quotes_exposure_cash_and_foreign_holdings_block(changes):
    assert next_intent(**args(**changes))["action"] == "HOLD"


def test_cent_rounding_rechecks_concentration_and_minimum():
    result = next_intent(**args(ask="12.499"))
    assert result["quantity"] == 2
    assert result["limit_price"] == "12.50"
    assert next_intent(**args(ask="99.999", account_equity="999.99"))["action"] == "HOLD"


def test_only_owned_terminal_shares_exit_and_no_same_day_reentry():
    result = next_intent(
        **args(
            owned_quantity=1,
            observed_quantity=2,
            entry_terminal=True,
            last_entry_day=date(2026, 10, 6),
        )
    )
    assert result["action"] == "SELL_INTENT_ONLY" and result["quantity"] == 1
    assert next_intent(**args(last_entry_day=date(2026, 10, 6)))["action"] == "HOLD"
    assert next_intent(**args(owned_quantity=1, observed_quantity=1))["action"] == "HOLD"


def test_intc_rejected_and_real_broker_mutations_remain_prohibited():
    kwargs = {
        "client_order_id": UUID(next_intent(**args())["client_order_id"]),
        "account_binding": "a" * 64,
        "side": "buy",
        "quantity": 1,
        "limit_price": Decimal(31),
    }
    with pytest.raises(ValidationError):
        PaperETFOrderIntent(**kwargs, symbol="INTC")
    intent = PaperETFOrderIntent(**kwargs)
    with pytest.raises(PaperStateError, match="Real order mutation remains blocked"):
        PaperOrderProtocol("fixture", "fixture").submit_fixture(intent)
    calls = []

    def respond(request):
        calls.append(request)
        body = intent.request()
        body.update(id="00000000-0000-0000-0000-000000000001", status="new", filled_qty="0")
        return httpx.Response(200, json=body)

    report = PaperOrderProtocol(
        "fixture", "fixture", transport=httpx.MockTransport(respond)
    ).submit_fixture(intent)
    assert not report["execution_available"] and len(calls) == 1
