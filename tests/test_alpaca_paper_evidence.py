from datetime import UTC, datetime, timedelta

import httpx
import pytest

from market_data.alpaca_paper_evidence import AlpacaPaperQuoteReader
from market_data.base import ProviderUnavailable

NOW = datetime(2026, 10, 2, 15, tzinfo=UTC)


def reader(payload, *, status=200):
    def handler(request):
        assert request.method == "GET" and request.url.host == "data.alpaca.markets"
        assert request.url.params["feed"] == "iex"
        assert request.url.params["symbols"] == "AAPL"
        return httpx.Response(status, json=payload,
                              headers={"Location": "https://api.alpaca.markets"})
    return AlpacaPaperQuoteReader("fixture-key", "fixture-secret",
                                transport=httpx.MockTransport(handler), clock=lambda: NOW)


def payload(age=0, bid="100.01", ask="100.02", symbol="AAPL"):
    return {"quotes": {symbol: {"bp": bid, "ap": ask,
            "t": (NOW-timedelta(seconds=age)).isoformat()}}}


def test_precise_observation_never_infers_status_or_execution():
    quote = reader(payload()).read("aapl")
    assert str(quote.bid) == "100.01" and quote.event_time == NOW
    assert len(quote.payload_sha256) == 64 and quote.received_time == NOW
    assert quote.market_status == "UNKNOWN" and not quote.execution_available
    assert quote.freshness_reasons(NOW) == ("QUOTE_STATUS_UNVERIFIED",)


@pytest.mark.parametrize("age,stale", [(30, False), (30.001, True), (31, True)])
def test_original_thirty_second_bound(age, stale):
    quote = reader(payload(age)).read("AAPL")
    assert ("QUOTE_TIME" in quote.freshness_reasons(NOW)) is stale
    assert "QUOTE_TIME" in quote.freshness_reasons(NOW-timedelta(seconds=1))


@pytest.mark.parametrize("data", [payload(-1), payload(bid="101"), payload(bid="0"),
    payload(bid="NaN"), payload(ask="Infinity"), payload(symbol="MSFT"),
    {"quotes": {"AAPL": None}}, {"quotes": {}}, {}])
def test_invalid_evidence_fails_closed(data):
    with pytest.raises(ProviderUnavailable, match="unavailable or invalid"):
        reader(data).read("AAPL")


@pytest.mark.parametrize("status", [302, 401, 403, 429, 500])
def test_no_redirect_retry_or_fallback(status):
    with pytest.raises(ProviderUnavailable):
        reader(payload(), status=status).read("AAPL")


def test_aware_event_time_required():
    data = payload()
    data["quotes"]["AAPL"]["t"] = "2026-10-02T15:00:00"
    with pytest.raises(ProviderUnavailable):
        reader(data).read("AAPL")
