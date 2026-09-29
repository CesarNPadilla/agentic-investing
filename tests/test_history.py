from datetime import UTC, datetime, timedelta
from decimal import Decimal

import httpx
import pytest
from pydantic import ValidationError

from market_data.alpaca import AlpacaMarketDataProvider
from market_data.base import ProviderUnavailable
from technical.history import DailyClose, PriceHistory, summarize


def test_known_moving_averages():
    bars = tuple(DailyClose(timestamp=datetime(2026, 1, 1, tzinfo=UTC)+timedelta(days=i), close=i+1) for i in range(50))
    result = summarize(PriceHistory(symbol='AAPL', bars=bars))
    assert result.sma20 == Decimal('40.5')
    assert result.sma50 == Decimal('25.5')
    assert result.state == 'sma20_above_sma50'
    assert summarize(PriceHistory(symbol='AAPL', bars=())) is None
    assert summarize(PriceHistory(symbol='AAPL', bars=bars[:19])).sma20 is None


def test_duplicate_bars_rejected():
    bar = DailyClose(timestamp=datetime(2026, 1, 1, tzinfo=UTC), close=1)
    with pytest.raises(ValidationError):
        PriceHistory(symbol='AAPL', bars=(bar, bar))


def test_history_paginates_and_excludes_current_session():
    calls = []
    def handle(request):
        calls.append(request)
        cutoff = datetime.fromisoformat(request.url.params['end'])
        assert request.url.params['adjustment'] == 'split'
        assert request.url.params['feed'] == 'iex'
        if len(calls) == 1:
            return httpx.Response(200, json={'symbol':'AAPL', 'bars':[{'t':(cutoff-timedelta(days=2)).isoformat(),'c':100}], 'next_page_token':'next'})
        assert request.url.params['page_token'] == 'next'
        return httpx.Response(200, json={'symbol':'AAPL', 'bars':[{'t':(cutoff-timedelta(days=1)).isoformat(),'c':101},{'t':cutoff.isoformat(),'c':102}], 'next_page_token':None})
    provider = AlpacaMarketDataProvider('key','secret',transport=httpx.MockTransport(handle))
    history = provider.get_history('AAPL')
    assert [b.close for b in history.bars] == [100,101]
    assert len(calls) == 2


def test_history_repeated_page_rejected():
    transport = httpx.MockTransport(lambda r: httpx.Response(200,json={'symbol':'AAPL','bars':[], 'next_page_token':'same'}))
    with pytest.raises(ProviderUnavailable):
        AlpacaMarketDataProvider('key','secret',transport=transport).get_history('AAPL')


def test_history_failure_keeps_quote_report():
    from agents.research import ResearchOrchestrator
    from market_data.sample import SampleMarketDataProvider
    class FailedHistory(SampleMarketDataProvider):
        def get_history(self, symbol):
            raise ProviderUnavailable('private')
    report = ResearchOrchestrator(FailedHistory()).research('AAPL')
    assert report.technicals is None
    assert 'price_history' in report.missing_data
    assert any('history unavailable' in warning for warning in report.risks)
