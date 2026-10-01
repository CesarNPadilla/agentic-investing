"""Immutable raw observations and separately sourced corporate actions."""

from datetime import date
from decimal import Decimal
from typing import Any

from pydantic import AwareDatetime, Field, model_validator

from portfolio.state import Record


class RawHistoricalPriceBar(Record):
    symbol: str
    timestamp: AwareDatetime
    open: Decimal = Field(gt=0)
    high: Decimal = Field(gt=0)
    low: Decimal = Field(gt=0)
    close: Decimal = Field(gt=0)
    volume: Decimal = Field(ge=0)
    feed: str
    adjustment_mode: str
    retrieved_at: AwareDatetime
    provider: str
    source_digest: str

    @model_validator(mode="after")
    def valid(self):
        if self.adjustment_mode != "raw":
            raise ValueError("Raw historical bar must use raw adjustment mode")
        if not self.low <= min(self.open, self.close) <= max(self.open, self.close) <= self.high:
            raise ValueError("Invalid OHLC")
        return self


class CorporateAction(Record):
    action_type: str
    symbol: str
    ex_date: date | None = None
    record_date: date | None = None
    payable_date: date | None = None
    process_date: date | None = None
    announced_at: AwareDatetime | None = None
    source: str
    retrieved_at: AwareDatetime
    source_digest: str
    availability_confidence: str


class HistoricalStatement(Record):
    symbol: str
    fiscal_period: str
    period_end: date
    filing_date: date | None
    accepted_at: AwareDatetime | None
    retrieved_at: AwareDatetime
    source: str
    raw_payload_digest: str
    normalized_values: dict[str, Decimal]
    currency: str | None
    statement_type: str
    amendment_indicator: str | None = None
    revision_proven: bool = False
    source_reference: str | None = None
    provider_metadata: dict[str, Any] = Field(default_factory=dict)
