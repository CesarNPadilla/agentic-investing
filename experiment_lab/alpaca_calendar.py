"""Alpaca exchange close adapter, independent of price bars and strategies."""

from datetime import UTC, date, datetime
from zoneinfo import ZoneInfo

import httpx

NEW_YORK = ZoneInfo("America/New_York")


class AlpacaTradingCalendarProvider:
    def __init__(self, api_key: str, api_secret: str, *, transport=None):
        if not api_key or not api_secret:
            raise ValueError("Alpaca credentials required")
        self._headers = {"APCA-API-KEY-ID": api_key, "APCA-API-SECRET-KEY": api_secret}
        self._transport = transport

    def closes(self, start: date, end: date) -> tuple[datetime, ...]:
        if start >= end or end >= datetime.now(UTC).date():
            raise ValueError("Past calendar range required")
        try:
            with httpx.Client(timeout=20, transport=self._transport) as client:
                response = client.get("https://paper-api.alpaca.markets/v2/calendar",
                                      headers=self._headers,
                                      params={"start": start.isoformat(), "end": end.isoformat(),
                                              "date_type": "TRADING"})
            if response.status_code != 200:
                raise ValueError("Calendar unavailable")
            payload = response.json()
        except (httpx.HTTPError, ValueError):
            raise ValueError("Alpaca calendar unavailable") from None
        if not isinstance(payload, list) or not payload:
            raise ValueError("Alpaca calendar unavailable")
        closes = []
        for day in payload:
            trading_day = date.fromisoformat(day["date"])
            local = datetime.fromisoformat(f"{trading_day}T{day['close']}").replace(
                tzinfo=NEW_YORK,
            )
            closes.append(local.astimezone(UTC))
        if tuple(sorted(set(closes))) != tuple(closes):
            raise ValueError("Alpaca calendar not ordered or unique")
        return tuple(closes)
