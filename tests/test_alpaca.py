from decimal import Decimal

import httpx
import pytest
from pydantic import ValidationError

from api.config import Settings
from market_data.alpaca import AlpacaMarketDataProvider
from market_data.base import ProviderUnavailable, SymbolNotFound


def provider(handler):
    return AlpacaMarketDataProvider('test-key', 'test-secret', transport=httpx.MockTransport(handler))


def test_trade_precision_and_feed():
    def handle(request):
        assert request.url.host == 'data.alpaca.markets'
        assert request.url.params['feed'] == 'iex'
        assert request.method == 'GET'
        return httpx.Response(200, text='{"symbol":"AAPL","trade":{"p":123.123456789,"t":"2026-01-01T12:00:00Z"}}')
    quote = provider(handle).get_quote('aapl')
    assert quote.price == Decimal('123.123456789')
    assert quote.source == 'alpaca-iex-last-trade'
    assert quote.is_sample is False
    assert quote.as_of.hour == 12


@pytest.mark.parametrize('status', [401, 403, 429, 500, 302])
def test_failed_requests_are_sanitized_without_retry(status):
    calls = []
    def handle(request):
        calls.append(request)
        return httpx.Response(status, text='test-secret')
    with pytest.raises(ProviderUnavailable) as error:
        provider(handle).get_quote('AAPL')
    assert 'test-secret' not in str(error.value)
    assert len(calls) == 1


@pytest.mark.parametrize('body', ['{}', 'null', '{"symbol":"MSFT"}', '{"symbol":"AAPL","trade":null}', '{"symbol":"AAPL","trade":{"p":-1,"t":"2026-01-01"}}'])
def test_bad_payload_fails_closed(body):
    with pytest.raises(ProviderUnavailable):
        provider(lambda r: httpx.Response(200, text=body)).get_quote('AAPL')


def test_missing_symbol():
    with pytest.raises(SymbolNotFound):
        provider(lambda r: httpx.Response(404)).get_quote('MISSING')


def test_timeout():
    def handle(request):
        raise httpx.ReadTimeout('private diagnostics')
    with pytest.raises(ProviderUnavailable, match='Alpaca market data unavailable'):
        provider(handle).get_quote('AAPL')


def test_credentials_required():
    with pytest.raises(ValidationError):
        Settings(_env_file=None, market_provider='alpaca')
