"""Replaceable read-only inputs for historical research; no broker dependency."""

from datetime import date
from typing import Protocol

from experiment_lab.historical_records import (
    CorporateAction,
    HistoricalStatement,
    RawHistoricalPriceBar,
)


class HistoricalPriceProvider(Protocol):
    def bars(self, symbols: tuple[str, ...], start: date, end: date) -> tuple[RawHistoricalPriceBar, ...]: ...


class HistoricalFundamentalProvider(Protocol):
    def statements(self, symbol: str, *, through: date) -> tuple[HistoricalStatement, ...]: ...


class CorporateActionProvider(Protocol):
    def actions(self, symbols: tuple[str, ...], start: date, end: date) -> tuple[CorporateAction, ...]: ...


class TradingCalendarProvider(Protocol):
    def closes(self, start: date, end: date) -> tuple: ...
