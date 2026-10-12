from datetime import UTC, datetime, timedelta

import httpx
import pytest
from pydantic import ValidationError

from integrations.brokers.alpaca_paper_activities import AlpacaPaperActivityReader, PaperActivities
from market_data.base import ProviderUnavailable
from portfolio.paper_fill_reconciliation import reconcile_fills

START = datetime(2026, 10, 5, 13, tzinfo=UTC)
END = START + timedelta(hours=1)


def fill(identifier="1", qty="1", cum="1", side="buy"):
    return {
        "activity_type": "FILL",
        "id": identifier,
        "order_id": "order-1",
        "symbol": "INTC",
        "qty": qty,
        "cum_qty": cum,
        "leaves_qty": "0",
        "price": "30",
        "side": side,
        "transaction_time": (START + timedelta(minutes=1)).isoformat(),
    }


def batch(rows):
    return PaperActivities(
        after=START,
        until=END,
        received_at=END,
        rows=rows,
        page_digests=(),
        pagination_exhausted=True,
    )


def test_partial_fills_replay_without_settlement_or_fee_inference():
    report = reconcile_fills(
        batch([fill(), fill("2", cum="2")]),
        opening_cash=1000,
        opening_positions={},
        closing_cash=940,
        closing_positions={"INTC": 2},
    )
    assert report["position_ledger_matches"] and report["trade_cash_matches"]
    assert not report["execution_available"] and not report["settlement_verified"]
    assert "SETTLED_CASH_UNVERIFIED" in report["blockers"]


def test_duplicate_and_fractional_fills_rejected():
    with pytest.raises(ValueError):
        reconcile_fills(
            batch([fill(), fill()]),
            opening_cash=1000,
            opening_positions={},
            closing_cash=940,
            closing_positions={},
        )
    with pytest.raises(ValidationError):
        reconcile_fills(
            batch([fill(qty="0.5")]),
            opening_cash=1000,
            opening_positions={},
            closing_cash=985,
            closing_positions={},
        )


def test_missing_fill_and_position_cash_mismatch_block():
    report = reconcile_fills(
        batch([fill(cum="2")]),
        opening_cash=1000,
        opening_positions={},
        closing_cash=900,
        closing_positions={"INTC": 3},
    )
    assert {
        "ORDER_FILL_HISTORY_INCOMPLETE",
        "CASH_LEDGER_MISMATCH",
        "POSITION_LEDGER_MISMATCH",
    } <= set(report["blockers"])


def test_unknown_activities_and_outside_interval_block():
    row = fill()
    row["transaction_time"] = (END + timedelta(seconds=1)).isoformat()
    report = reconcile_fills(
        batch([row, {"activity_type": "FEE", "id": "fee"}]),
        opening_cash=1000,
        opening_positions={},
        closing_cash=1000,
        closing_positions={},
    )
    assert {"FILL_OUTSIDE_REPLAY_INTERVAL", "NONFILL_ACTIVITY_REQUIRES_MAPPING"} <= set(
        report["blockers"]
    )


def test_pagination_exhaustion_and_fixed_paper_host():
    calls = []

    def handler(request):
        assert request.method == "GET" and request.url.host == "paper-api.alpaca.markets"
        calls.append(request)
        rows = [{"id": str(i)} for i in range(100)] if len(calls) == 1 else []
        return httpx.Response(200, json=rows)

    result = AlpacaPaperActivityReader(
        "key", "secret", transport=httpx.MockTransport(handler), clock=lambda: END
    ).read(after=START, until=END)
    assert result.pagination_exhausted and len(result.rows) == 100
    assert calls[1].url.params["page_token"] == "99"


def test_repeated_pages_fail_closed():
    def handler(request):
        return httpx.Response(200, json=[{"id": str(i)} for i in range(100)])

    with pytest.raises(ProviderUnavailable):
        AlpacaPaperActivityReader(
            "k", "s", transport=httpx.MockTransport(handler), clock=lambda: END
        ).read(after=START, until=END)


@pytest.mark.parametrize("status", [302, 401, 403, 429, 500])
def test_http_failures_no_fallback(status):
    with pytest.raises(ProviderUnavailable):
        AlpacaPaperActivityReader(
            "k",
            "s",
            transport=httpx.MockTransport(lambda r: httpx.Response(status)),
            clock=lambda: END,
        ).read(after=START, until=END)
