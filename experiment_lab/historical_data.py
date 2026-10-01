"""Provider-neutral, point-in-time historical inputs for research simulations.

The provider is responsible for exchange close instants and adjustment vintages.
An adjusted series downloaded today must never be described as known in 2020.
"""

import json
from datetime import datetime
from decimal import Decimal
from pathlib import Path
from typing import Protocol

from pydantic import AwareDatetime, Field, model_validator

from market_data.models import Symbol
from portfolio.state import Identifier, Record
from risk.evaluator import digest


class MarketBar(Record):
    symbol: Symbol
    session_close: AwareDatetime
    available_at: AwareDatetime
    adjustment_known_at: AwareDatetime
    open: Decimal = Field(gt=0)
    high: Decimal = Field(gt=0)
    low: Decimal = Field(gt=0)
    close: Decimal = Field(gt=0)
    volume: Decimal = Field(ge=0)

    @model_validator(mode="after")
    def ordered(self):
        if not self.low <= min(self.open, self.close) <= max(self.open, self.close) <= self.high:
            raise ValueError("Invalid adjusted OHLC")
        if self.available_at < self.session_close:
            raise ValueError("Bar available before exchange close")
        return self


class FundamentalPoint(Record):
    symbol: Symbol
    metric: Identifier
    value: Decimal
    period_end: AwareDatetime
    published_at: AwareDatetime
    available_at: AwareDatetime
    source_id: Identifier

    @model_validator(mode="after")
    def ordered(self):
        if self.period_end > self.published_at or self.published_at > self.available_at:
            raise ValueError("Fundamental observation predates its source")
        return self


class HistoricalResearchDataset(Record):
    dataset_id: Identifier
    version: Identifier
    provider: Identifier
    calendar_id: Identifier
    adjustment: str
    acquired_at: AwareDatetime
    sessions: tuple[AwareDatetime, ...]
    bars: tuple[MarketBar, ...]
    fundamentals: tuple[FundamentalPoint, ...] = ()
    # The source must attest both histories. Missing attestations fail validation.
    corporate_actions_complete: bool = False
    session_calendar_complete: bool = False
    point_in_time_adjustments: bool = False
    point_in_time_fundamentals: bool = False
    is_synthetic: bool = True

    @model_validator(mode="after")
    def validate_history(self):
        if not self.sessions or tuple(sorted(set(self.sessions))) != self.sessions:
            raise ValueError("Unordered or duplicate exchange sessions")
        keys = [(b.symbol, b.session_close) for b in self.bars]
        if len(set(keys)) != len(keys):
            raise ValueError("Duplicate symbol/session bars")
        if any(b.session_close not in self.sessions for b in self.bars):
            raise ValueError("Bar outside the exchange calendar")
        if self.adjustment != "all":
            raise ValueError("Fully adjusted OHLCV required")
        if self.is_synthetic:
            raise ValueError("Historical research input cannot be synthetic")
        if any(b.available_at > self.acquired_at or b.adjustment_known_at > self.acquired_at
               for b in self.bars):
            raise ValueError("Bar vintage postdates dataset acquisition")
        if any(f.available_at > self.acquired_at for f in self.fundamentals):
            raise ValueError("Fundamental vintage postdates dataset acquisition")
        return self

    def quality_findings(self, symbols: tuple[str, ...], start: datetime, end: datetime):
        selected = tuple(s for s in self.sessions if start <= s <= end)
        findings = set()
        if not self.session_calendar_complete:
            findings.add("EXCHANGE_CALENDAR_UNVERIFIED")
        if not self.corporate_actions_complete:
            findings.add("CORPORATE_ACTIONS_INCOMPLETE")
        if not self.point_in_time_adjustments:
            findings.add("ADJUSTMENT_VINTAGE_UNVERIFIED")
        if not self.point_in_time_fundamentals:
            findings.add("FUNDAMENTAL_VINTAGE_UNVERIFIED")
        for symbol in symbols:
            observed = {b.session_close for b in self.bars if b.symbol == symbol}
            if not selected or not set(selected) <= observed:
                findings.add("MISSING_SESSIONS:" + symbol)
        if any(
            b.adjustment_known_at > b.available_at
            for b in self.bars if b.session_close in selected
        ):
            findings.add("RETROSPECTIVE_ADJUSTMENT")
        return tuple(sorted(findings))

    @property
    def content_digest(self):
        return digest(self)


class HistoricalResearchProvider(Protocol):
    def load(self, dataset_id: str, version: str) -> HistoricalResearchDataset: ...


class JsonHistoricalResearchProvider:
    """Read an immutable provider export, never invent timestamps or attestations."""

    def __init__(self, path: Path):
        self.path = path

    def load(self, dataset_id: str, version: str) -> HistoricalResearchDataset:
        payload = json.loads(self.path.read_text(encoding="utf-8"))
        dataset = HistoricalResearchDataset.model_validate(payload)
        if (dataset.dataset_id, dataset.version) != (dataset_id, version):
            raise ValueError("Provider export identity mismatch")
        return dataset
