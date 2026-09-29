"""Read-only US equity last trades from Alpaca's IEX feed."""

import json
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from zoneinfo import ZoneInfo

import httpx
from pydantic import TypeAdapter

from market_data.base import ProviderUnavailable, SymbolNotFound
from market_data.models import Quote, Symbol
from technical.history import DailyClose, PriceHistory


class AlpacaMarketDataProvider:
    def get_history(self, symbol: str) -> PriceHistory:
        symbol = TypeAdapter(Symbol).validate_python(symbol)
        # Exclude today's New York session, even when the market is already closed.
        cutoff = datetime.now(ZoneInfo("America/New_York")).replace(
            hour=0, minute=0, second=0, microsecond=0
        ).astimezone(UTC)
        start = cutoff - timedelta(days=180)
        params = {"feed": "iex", "currency": "USD", "timeframe": "1Day",
                  "adjustment": "split", "sort": "asc", "limit": "1000",
                  "start": start.isoformat(), "end": cutoff.isoformat()}
        bars = []
        seen = set()
        try:
            with httpx.Client(timeout=10, transport=self._transport) as client:
                for _ in range(5):
                    response = client.get(
                        f"https://data.alpaca.markets/v2/stocks/{symbol}/bars",
                        params=params, headers=self._headers,
                    )
                    if response.status_code != 200:
                        raise ProviderUnavailable("Alpaca history unavailable")
                    data = json.loads(response.text, parse_float=Decimal)
                    if data["symbol"] != symbol:
                        raise ValueError("Symbol mismatch")
                    for row in data["bars"] or []:
                        bar = DailyClose(timestamp=row["t"], close=row["c"])
                        if start <= bar.timestamp < cutoff:
                            bars.append(bar)
                    token = data.get("next_page_token")
                    if not token:
                        return PriceHistory(symbol=symbol, bars=tuple(bars))
                    if not isinstance(token, str) or token in seen:
                        raise ValueError("Invalid pagination")
                    seen.add(token)
                    params["page_token"] = token
            raise ProviderUnavailable("History pagination limit reached")
        except (httpx.HTTPError, ValueError, KeyError, TypeError):
            raise ProviderUnavailable("Alpaca history unavailable") from None

    def __init__(self, api_key: str, api_secret: str, *, transport=None):
        self._headers = {"APCA-API-KEY-ID": api_key, "APCA-API-SECRET-KEY": api_secret}
        self._transport = transport

    def get_quote(self, symbol: str) -> Quote:
        symbol = TypeAdapter(Symbol).validate_python(symbol)
        try:
            # No automatic retries: quota/auth failures must not amplify traffic.
            with httpx.Client(timeout=10, transport=self._transport) as client:
                response = client.get(
                    f"https://data.alpaca.markets/v2/stocks/{symbol}/trades/latest",
                    params={"feed": "iex", "currency": "USD"}, headers=self._headers,
                )
            if response.status_code == 404:
                raise SymbolNotFound(symbol)
            if response.status_code != 200:
                raise ProviderUnavailable("Alpaca market data unavailable")
            data = json.loads(response.text, parse_float=Decimal)
            if data["symbol"] != symbol:
                raise ValueError("Symbol mismatch")
            return Quote(
                symbol=symbol, price=data["trade"]["p"], currency="USD",
                as_of=data["trade"]["t"], source="alpaca-iex-last-trade", is_sample=False,
            )
        except (httpx.HTTPError, ValueError, KeyError, TypeError) as exc:
            if isinstance(exc, SymbolNotFound):
                raise
            raise ProviderUnavailable("Alpaca market data unavailable") from None
