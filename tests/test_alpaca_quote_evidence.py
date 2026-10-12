from datetime import UTC, datetime, timedelta
import httpx
import pytest
from market_data.alpaca_evidence import AlpacaPaperQuoteReader
from market_data.base import ProviderUnavailable

NOW = datetime(2026, 10, 2, 15, tzinfo=UTC)


def reader(row=None, *, status=200, symbol="AAPL"):
    def handler(request):
        assert request.method == "GET" and request.url.host == "data.alpaca.markets"
        assert request.url.params["feed"] == "iex"
        return httpx.Response(status, json={"quotes": {symbol: row or {
            "bp": 100, "ap": 101, "t": NOW.isoformat()}}})
    return AlpacaPaperQuoteReader("key", "secret", transport=httpx.MockTransport(handler), clock=lambda: NOW)


def test_bid_ask_receipt_and_unknown_status_never_authorize_execution():
    quote = reader().read("AAPL")
    assert quote.bid == 100 and quote.ask == 101 and quote.received_time == NOW
    assert quote.market_status == "UNKNOWN" and not quote.execution_available
    assert "QUOTE_TIME" not in quote.blockers(NOW + timedelta(seconds=30))
    assert "QUOTE_TIME" in quote.blockers(NOW + timedelta(seconds=30, microseconds=1))
    assert "MARKET_STATUS_UNVERIFIED" in quote.blockers(NOW)


@pytest.mark.parametrize("row", [
    {"bp": 102, "ap": 101, "t": NOW.isoformat()},
    {"bp": 0, "ap": 101, "t": NOW.isoformat()},
    {"bp": "NaN", "ap": 101, "t": NOW.isoformat()},
    {"bp": 100, "ap": 101, "t": "2026-10-02T15:00:00"},
    {"bp": 100, "ap": 101, "t": (NOW+timedelta(seconds=1)).isoformat()},
    {"bp": 100, "t": NOW.isoformat()},
])
def test_invalid_quotes_fail_closed(row):
    with pytest.raises(ProviderUnavailable): reader(row).read("AAPL")


@pytest.mark.parametrize("status", [302, 401, 403, 429, 500])
def test_no_fallback_on_http_failure(status):
    with pytest.raises(ProviderUnavailable): reader(status=status).read("AAPL")


def test_wrong_symbol_rejected():
    with pytest.raises(ProviderUnavailable): reader(symbol="MSFT").read("AAPL")
