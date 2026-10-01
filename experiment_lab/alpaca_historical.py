"""Read-only Alpaca market history acquisition; never attests unavailable vintages.

Alpaca's daily-bar timestamp labels the trading day rather than its close. The
calendar endpoint supplies the actual close, including early closes. The API does
not attest when a retrospective adjusted OHLCV vintage became historically known.
"""

import hashlib
import json
from datetime import UTC, date, datetime
from decimal import Decimal
from zoneinfo import ZoneInfo

import httpx

from experiment_lab.historical_data import HistoricalResearchDataset, MarketBar
from experiment_lab.historical_records import RawHistoricalPriceBar

NEW_YORK = ZoneInfo("America/New_York")


class AlpacaHistoricalResearchProvider:
    def __init__(self, api_key: str, api_secret: str, *, feed="iex", transport=None,
                 symbols: tuple[str, ...] = (), start: date | None = None,
                 end: date | None = None):
        if not api_key or not api_secret:
            raise ValueError("Alpaca market-data credentials required")
        if feed not in {"iex", "sip"}:
            raise ValueError("Explicit IEX or SIP feed required")
        self.headers = {"APCA-API-KEY-ID": api_key, "APCA-API-SECRET-KEY": api_secret}
        self.feed = feed
        self.transport = transport
        self.symbols = symbols
        self.start = start
        self.end = end

    def load(self, dataset_id: str, version: str) -> HistoricalResearchDataset:
        if self.start is None or self.end is None or not self.symbols:
            raise ValueError("Alpaca historical range and symbols must be configured")
        return self.load_range(dataset_id, version, self.symbols, self.start, self.end)

    def _get(self, client, url, params):
        try:
            response = client.get(url, headers=self.headers, params=params)
            if response.status_code != 200:
                raise ValueError(f"Alpaca historical read failed: HTTP {response.status_code}")
            return json.loads(response.text, parse_float=Decimal)
        except (httpx.HTTPError, ValueError) as error:
            raise ValueError("Alpaca historical market data unavailable") from error

    def load_range(self, dataset_id: str, version: str, symbols: tuple[str, ...],
                   start: date, end: date) -> HistoricalResearchDataset:
        """Retrieve completed sessions only; mark unproven PIT/action data false."""
        if start >= end or end >= datetime.now(UTC).date():
            raise ValueError("An ordered, fully past date range is required")
        if not symbols or len(set(symbols)) != len(symbols):
            raise ValueError("Unique symbols required")
        with httpx.Client(timeout=20, transport=self.transport) as client:
            calendar = self._get(
                client, "https://paper-api.alpaca.markets/v2/calendar",
                {"start": start.isoformat(), "end": end.isoformat(), "date_type": "TRADING"},
            )
            if not isinstance(calendar, list) or not calendar:
                raise ValueError("Missing Alpaca exchange calendar")
            closes = {}
            for day in calendar:
                trading_day = date.fromisoformat(day["date"])
                local_close = datetime.fromisoformat(
                    f"{trading_day.isoformat()}T{day['close']}"
                ).replace(tzinfo=NEW_YORK)
                closes[trading_day] = local_close.astimezone(UTC)
            sessions = tuple(sorted(closes.values()))
            observations = []
            for symbol in symbols:
                params = {
                    "timeframe": "1Day", "start": start.isoformat(),
                    "end": end.isoformat(), "adjustment": "all", "feed": self.feed,
                    "currency": "USD", "sort": "asc", "limit": "10000", "asof": "-",
                }
                seen_tokens = set()
                while True:
                    payload = self._get(
                        client, f"https://data.alpaca.markets/v2/stocks/{symbol}/bars",
                        params,
                    )
                    if payload.get("symbol") != symbol:
                        raise ValueError("Alpaca symbol mismatch")
                    for row in payload.get("bars") or ():
                        bar_date = datetime.fromisoformat(row["t"])\
                            .astimezone(NEW_YORK).date()
                        if bar_date not in closes:
                            raise ValueError("Bar outside supplied exchange calendar")
                        observations.append((symbol, closes[bar_date], row))
                    token = payload.get("next_page_token")
                    if not token:
                        break
                    if not isinstance(token, str) or token in seen_tokens:
                        raise ValueError("Invalid historical pagination")
                    seen_tokens.add(token)
                    params["page_token"] = token
        acquired = datetime.now(UTC)
        bars = tuple(MarketBar(
            symbol=symbol, session_close=close,
            # Retrieval is the only proven availability/vintage instant.
            available_at=acquired, adjustment_known_at=acquired,
            open=row["o"], high=row["h"], low=row["l"],
            close=row["c"], volume=row["v"],
        ) for symbol, close, row in observations)
        return HistoricalResearchDataset(
            dataset_id=dataset_id, version=version,
            provider=f"alpaca-{self.feed}-daily-adjusted-all", calendar_id="alpaca-us-trading",
            adjustment="all", acquired_at=acquired, sessions=sessions,
            bars=tuple(bars), fundamentals=(), corporate_actions_complete=False,
            session_calendar_complete=True, point_in_time_adjustments=False,
            point_in_time_fundamentals=False, is_synthetic=False,
        )


class AlpacaRawPriceProvider(AlpacaHistoricalResearchProvider):
    """Raw, retrieval-vintaged daily observations, separate from actions."""

    def bars(self, symbols: tuple[str, ...], start: date, end: date) -> tuple[RawHistoricalPriceBar, ...]:
        if start >= end or end >= datetime.now(UTC).date():
            raise ValueError("An ordered, fully past range is required")
        observations = []
        with httpx.Client(timeout=20, transport=self.transport) as client:
            for symbol in symbols:
                params = {"timeframe": "1Day", "start": start.isoformat(),
                          "end": end.isoformat(), "adjustment": "raw", "feed": self.feed,
                          "currency": "USD", "sort": "asc", "limit": "10000"}
                seen_tokens = set()
                while True:
                    payload = self._get(client,
                                        f"https://data.alpaca.markets/v2/stocks/{symbol}/bars",
                                        params)
                    if payload.get("symbol") != symbol:
                        raise ValueError("Alpaca symbol mismatch")
                    retrieved_at = datetime.now(UTC)
                    for row in payload.get("bars") or ():
                        stamp = datetime.fromisoformat(row["t"])
                        if not start <= stamp.astimezone(NEW_YORK).date() <= end:
                            raise ValueError("Bar outside requested date range")
                        raw = json.dumps(row, sort_keys=True, separators=(",", ":"),
                                         default=str).encode()
                        observations.append(RawHistoricalPriceBar(
                            symbol=symbol, timestamp=stamp, open=row["o"], high=row["h"],
                            low=row["l"], close=row["c"], volume=row["v"],
                            feed=self.feed, adjustment_mode="raw", retrieved_at=retrieved_at,
                            provider="Alpaca", source_digest=hashlib.sha256(raw).hexdigest(),
                        ))
                    token = payload.get("next_page_token")
                    if not token:
                        break
                    if not isinstance(token, str) or token in seen_tokens:
                        raise ValueError("Invalid historical pagination")
                    seen_tokens.add(token)
                    params["page_token"] = token
        return tuple(observations)
