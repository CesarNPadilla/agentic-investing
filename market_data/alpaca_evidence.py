"""Read-only IEX bid/ask acquisition for paper qualification, with no status inference."""
import hashlib
import json
from datetime import UTC, datetime
from decimal import Decimal
from typing import Literal

import httpx
from pydantic import BaseModel, ConfigDict, Field, TypeAdapter, model_validator

from market_data.base import ProviderUnavailable
from market_data.models import Symbol


class PaperQuoteEvidence(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    symbol: Symbol
    source: Literal["alpaca-iex-best-bid-ask"] = "alpaca-iex-best-bid-ask"
    currency: Literal["USD"] = "USD"
    bid: Decimal = Field(gt=0, allow_inf_nan=False)
    ask: Decimal = Field(gt=0, allow_inf_nan=False)
    event_time: datetime
    received_time: datetime
    raw_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    market_status: Literal["UNKNOWN"] = "UNKNOWN"
    execution_available: Literal[False] = False

    @model_validator(mode="after")
    def coherent(self):
        if any(t.tzinfo is None or t.utcoffset() is None for t in (self.event_time, self.received_time)):
            raise ValueError("Aware timestamps required")
        if self.bid > self.ask or self.event_time > self.received_time:
            raise ValueError("Crossed or future quote")
        return self

    def blockers(self, now: datetime):
        if now.tzinfo is None or now.utcoffset() is None:
            raise ValueError("Aware evaluation time required")
        reasons = ["MARKET_STATUS_UNVERIFIED", "RUNTIME_INTEGRATION_PENDING"]
        if self.received_time > now or not 0 <= (now-self.event_time).total_seconds() <= 30:
            reasons.append("QUOTE_TIME")
        return tuple(reasons)


class AlpacaPaperQuoteReader:
    def __init__(self, key: str, secret: str, *, transport=None, clock=None):
        if not key.strip() or not secret.strip():
            raise ValueError("Credentials required")
        self._headers = {"APCA-API-KEY-ID": key, "APCA-API-SECRET-KEY": secret}
        self._transport = transport
        self._clock = clock or (lambda: datetime.now(UTC))

    def read(self, symbol: str):
        symbol = TypeAdapter(Symbol).validate_python(symbol)
        try:
            with httpx.Client(timeout=15, transport=self._transport, follow_redirects=False) as client:
                response = client.get("https://data.alpaca.markets/v2/stocks/quotes/latest",
                    params={"symbols": symbol, "feed": "iex", "currency": "USD"}, headers=self._headers)
            receipt = self._clock()
            if response.status_code != 200:
                raise ValueError("Quote unavailable")
            data = json.loads(response.content, parse_float=Decimal)
            if set(data["quotes"]) != {symbol}:
                raise ValueError("Symbol mismatch")
            row = data["quotes"][symbol]
            # Preserve the raw bytes digest; datetime normalization is microsecond precision.
            return PaperQuoteEvidence(symbol=symbol, bid=row["bp"], ask=row["ap"],
                event_time=row["t"], received_time=receipt,
                raw_sha256=hashlib.sha256(response.content).hexdigest())
        except (httpx.HTTPError, ValueError, KeyError, TypeError):
            raise ProviderUnavailable("Alpaca paper quote unavailable or invalid") from None
