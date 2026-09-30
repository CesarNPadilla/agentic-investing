"""Deterministic point-in-time adjusted OHLCV; calendar supplied by a trusted adapter."""

import itertools
from datetime import datetime
from decimal import Decimal
from typing import Literal

from pydantic import AwareDatetime, Field, model_validator

from market_data.models import Symbol
from portfolio.state import Identifier, Nonnegative, Record
from technical.history import _ema


class SessionBar(Record):
    session_close: AwareDatetime
    available_at: AwareDatetime
    open: Decimal = Field(gt=0, allow_inf_nan=False)
    high: Decimal = Field(gt=0, allow_inf_nan=False)
    low: Decimal = Field(gt=0, allow_inf_nan=False)
    close: Decimal = Field(gt=0, allow_inf_nan=False)
    volume: Nonnegative

    @model_validator(mode="after")
    def valid(self):
        if not self.low <= min(self.open, self.close) <= max(self.open, self.close) <= self.high:
            raise ValueError("Inconsistent OHLC")
        if self.available_at < self.session_close:
            raise ValueError("Incomplete daily session")
        return self


class SessionHistory(Record):
    symbol: Symbol
    source: Identifier
    calendar_id: Identifier
    # Exact exchange close instants, including holidays and early closes, not weekdays.
    sessions: tuple[AwareDatetime, ...] = Field(min_length=1)
    bars: tuple[SessionBar, ...]
    adjustment: Literal["all", "split", "raw"]
    adjustment_known_at: AwareDatetime
    reliable: bool = False
    is_sample: bool = False

    @model_validator(mode="after")
    def ordered(self):
        times = tuple(b.session_close for b in self.bars)
        if tuple(sorted(set(self.sessions))) != self.sessions:
            raise ValueError("Calendar must be ordered and unique")
        if tuple(sorted(set(times))) != times or not set(times) <= set(self.sessions):
            raise ValueError("Bars must be ordered unique calendar sessions")
        return self


class IndicatorSnapshot(Record):
    symbol: Symbol
    as_of: AwareDatetime
    data_timestamp: AwareDatetime | None
    history_digest: str
    period: int
    status: Literal["AVAILABLE", "INSUFFICIENT_DATA"]
    values: dict[str, Decimal | None]
    missing_data: tuple[str, ...]


class TechnicalIndicatorService:
    def calculate(
        self,
        history: SessionHistory,
        *,
        as_of: datetime,
        period=14,
        annual_sessions=252,
        benchmark: SessionHistory | None = None,
        allow_test_data=False,
    ) -> IndicatorSnapshot:
        from risk.evaluator import digest

        if as_of.tzinfo is None or as_of.utcoffset() is None or period < 2 or annual_sessions <= 0:
            raise ValueError("Aware cutoff and valid calculation parameters required")
        expected = tuple(s for s in history.sessions if s <= as_of)
        bars = tuple(
            b for b in history.bars if b.session_close <= as_of and b.available_at <= as_of
        )
        gaps = []
        if not history.reliable or (history.is_sample and not allow_test_data):
            gaps.append("unreliable_history")
        if history.adjustment != "all" or history.adjustment_known_at > as_of:
            gaps.append("point_in_time_adjustments")
        if tuple(b.session_close for b in bars) != expected or not expected:
            gaps.append("missing_completed_sessions")
        values = dict.fromkeys(
            (
                "sma",
                "ema",
                "rsi",
                "atr",
                "historical_volatility",
                "relative_strength",
                "volume_average",
                "price_return",
                "drawdown",
            )
        )
        closes = [b.close for b in bars]
        if len(bars) < period + 1:
            gaps.append("insufficient_history")
        if not gaps:
            values["sma"] = sum(closes[-period:]) / period
            values["ema"] = list(_ema(closes, period).values())[-1]
            changes = [b - a for a, b in itertools.pairwise(closes)]
            gain = sum(max(c, Decimal(0)) for c in changes[:period]) / period
            loss = sum(max(-c, Decimal(0)) for c in changes[:period]) / period
            ranges = [
                max(b.high - b.low, abs(b.high - a.close), abs(b.low - a.close))
                for a, b in itertools.pairwise(bars)
            ]
            atr = sum(ranges[:period]) / period
            for change, tr in zip(changes[period:], ranges[period:]):
                gain = (gain * (period - 1) + max(change, Decimal(0))) / period
                loss = (loss * (period - 1) + max(-change, Decimal(0))) / period
                atr = (atr * (period - 1) + tr) / period
            values["rsi"] = (
                Decimal(50)
                if not gain and not loss
                else Decimal(100)
                if not loss
                else 100 - 100 / (1 + gain / loss)
            )
            values["atr"] = atr
            returns = [b / a - 1 for a, b in zip(closes[-period - 1 :], closes[-period:])]
            mean = sum(returns) / period
            values["historical_volatility"] = (
                sum((r - mean) ** 2 for r in returns) / (period - 1) * annual_sessions
            ).sqrt()
            values["price_return"] = closes[-1] / closes[-period - 1] - 1
            values["volume_average"] = sum(b.volume for b in bars[-period:]) / period
            peak, worst = closes[0], Decimal(0)
            for close in closes:
                peak = max(peak, close)
                worst = min(worst, close / peak - 1)
            values["drawdown"] = worst
            if benchmark is not None:
                other = self.calculate(
                    benchmark,
                    as_of=as_of,
                    period=period,
                    annual_sessions=annual_sessions,
                    allow_test_data=allow_test_data,
                )
                other_times = tuple(s for s in benchmark.sessions if s <= as_of)
                if other.status == "AVAILABLE" and expected == other_times:
                    values["relative_strength"] = (1 + values["price_return"]) / (
                        1 + other.values["price_return"]
                    ) - 1
                else:
                    gaps.append("benchmark_alignment_or_quality")
        return IndicatorSnapshot(
            symbol=history.symbol,
            as_of=as_of,
            data_timestamp=bars[-1].session_close if bars else None,
            history_digest=digest((history, as_of, period, annual_sessions, benchmark)),
            period=period,
            status="INSUFFICIENT_DATA" if gaps else "AVAILABLE",
            values=values,
            missing_data=tuple(gaps)
            + (("relative_strength_benchmark",) if benchmark is None else ()),
        )
