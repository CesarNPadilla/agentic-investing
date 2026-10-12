"""Read-only IEX bid/ask observations; not execution-qualified market status."""
import hashlib
import json
from datetime import UTC, datetime
from decimal import Decimal
from typing import Literal

import httpx
from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, TypeAdapter, model_validator

from market_data.base import ProviderUnavailable
from market_data.models import Symbol


class PaperQuoteObservation(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    symbol: Symbol
    bid: Decimal = Field(gt=0, allow_inf_nan=False)
    ask: Decimal = Field(gt=0, allow_inf_nan=False)
    event_time: AwareDatetime
    received_time: AwareDatetime
    source: Literal["alpaca-iex-bid-ask"] = "alpaca-iex-bid-ask"
    currency: Literal["USD"] = "USD"
    market_status: Literal["UNKNOWN"] = "UNKNOWN"
    payload_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    execution_available: Literal[False] = False

    @model_validator(mode="after")
    def coherent(self):
        if self.bid > self.ask or self.event_time > self.received_time:
            raise ValueError("Crossed quote or future event")
        return self

    def freshness_reasons(self, now: datetime) -> tuple[str, ...]:
        if now.tzinfo is None or now.utcoffset() is None:
            raise ValueError("Aware evaluation time required")
        reasons = []
        if self.received_time > now or not 0 <= (now-self.event_time).total_seconds() <= 30:
            reasons.append("QUOTE_TIME")
        # A successful quote HTTP response never proves absence of a halt.
        reasons.append("QUOTE_STATUS_UNVERIFIED")
        return tuple(reasons)


class AlpacaPaperQuoteReader:
    def __init__(self, api_key: str, api_secret: str, *, transport=None,
                 clock=lambda: datetime.now(UTC)):
        if not api_key.strip() or not api_secret.strip():
            raise ValueError("Alpaca credentials required")
        self._headers = {"APCA-API-KEY-ID": api_key, "APCA-API-SECRET-KEY": api_secret}
        self._transport = transport
        self._clock = clock

    def read(self, symbol: str) -> PaperQuoteObservation:
        symbol = TypeAdapter(Symbol).validate_python(symbol)
        try:
            with httpx.Client(timeout=10, transport=self._transport, follow_redirects=False) as client:
                response = client.get("https://data.alpaca.markets/v2/stocks/quotes/latest",
                                      params={"symbols": symbol, "feed": "iex", "currency": "USD"},
                                      headers=self._headers)
            received = self._clock()
            if response.status_code != 200:
                raise ValueError("Quote unavailable")
            payload = json.loads(response.content, parse_float=Decimal)
            quotes = payload["quotes"]
            if not isinstance(quotes, dict) or set(quotes) != {symbol}:
                raise ValueError("Unexpected quote symbols")
            quote = quotes[symbol]
            return PaperQuoteObservation(symbol=symbol, bid=quote["bp"], ask=quote["ap"],
                event_time=quote["t"], received_time=received,
                payload_sha256=hashlib.sha256(response.content).hexdigest())
        except (httpx.HTTPError, ValueError, KeyError, TypeError):
            raise ProviderUnavailable("Alpaca IEX quote unavailable or invalid") from None
