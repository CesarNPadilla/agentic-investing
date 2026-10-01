"""Offline provider response checks; no market request or credentials in tests."""

from datetime import date

import httpx

from experiment_lab.alpaca_historical import AlpacaHistoricalResearchProvider


def test_daily_bar_maps_to_actual_early_close_and_does_not_claim_pit():
    def handle(request):
        if request.url.path == "/v2/calendar":
            return httpx.Response(200, json=[
                {"date": "2020-11-27", "open": "09:30", "close": "13:00"},
                {"date": "2020-11-30", "open": "09:30", "close": "16:00"},
            ])
        assert request.url.params["adjustment"] == "all"
        assert request.url.params["feed"] == "iex"
        return httpx.Response(200, json={"symbol": "AAPL", "bars": [
            {"t": "2020-11-27T05:00:00Z", "o": 100, "h": 101,
             "l": 99, "c": 100, "v": 1000},
            {"t": "2020-11-30T05:00:00Z", "o": 101, "h": 102,
             "l": 100, "c": 101, "v": 1200},
        ], "next_page_token": None})

    adapter = AlpacaHistoricalResearchProvider(
        "test-key", "test-secret", transport=httpx.MockTransport(handle)
    )
    dataset = adapter.load_range(
        "alpaca-test", "1", ("AAPL",), date(2020, 11, 27), date(2020, 11, 30)
    )
    assert dataset.sessions[0].isoformat() == "2020-11-27T18:00:00+00:00"
    assert dataset.sessions[1].isoformat() == "2020-11-30T21:00:00+00:00"
    assert not dataset.point_in_time_adjustments
    assert not dataset.corporate_actions_complete
    assert all(b.adjustment_known_at == dataset.acquired_at for b in dataset.bars)
