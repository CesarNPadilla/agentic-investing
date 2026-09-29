"""Daily close history and deterministic moving averages."""

from decimal import Decimal
from itertools import pairwise
from typing import Literal
from zoneinfo import ZoneInfo

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, model_validator

from market_data.models import Symbol


class DailyClose(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    timestamp: AwareDatetime
    close: Decimal = Field(gt=0, allow_inf_nan=False)


class PriceHistory(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    symbol: Symbol
    source: str = Field(default="alpaca-iex", min_length=1, max_length=200)
    adjustment: Literal["split", "all", "raw"] = "split"
    is_sample: bool = False
    timeframe: Literal["1Day"] = "1Day"
    bars: tuple[DailyClose, ...] = Field(max_length=5000)

    @model_validator(mode="after")
    def ordered(self):
        times = [bar.timestamp for bar in self.bars]
        if times != sorted(set(times)):
            raise ValueError("Daily bars must be unique and chronological")
        days = [time.astimezone(ZoneInfo("America/New_York")).date() for time in times]
        if len(days) != len(set(days)):
            raise ValueError("Only one close per New York calendar day is allowed")
        return self


class HistoryEvidence(PriceHistory):
    """JSON callers must declare provenance and adjustment explicitly."""

    source: str = Field(min_length=1, max_length=200)
    adjustment: Literal["split", "all", "raw"]
    is_sample: bool


class TechnicalSummary(BaseModel):
    bars_used: int
    as_of: AwareDatetime
    sma20: Decimal | None = None
    sma50: Decimal | None = None
    rsi14: Decimal | None = None
    macd: Decimal | None = None
    macd_signal: Decimal | None = None
    macd_histogram: Decimal | None = None
    bollinger_upper: Decimal | None = None
    bollinger_lower: Decimal | None = None
    return_20: Decimal | None = None
    volatility_20_annualized: Decimal | None = None
    max_drawdown: Decimal | None = None
    drawdown_from_peak: Decimal | None = None
    missing_indicators: list[str] = Field(default_factory=list)
    state: str = "insufficient_history"


def summarize(history: PriceHistory) -> TechnicalSummary | None:
    if not history.bars:
        return None
    closes = [bar.close for bar in history.bars]
    sma20 = sum(closes[-20:]) / Decimal(20) if len(closes) >= 20 else None
    sma50 = sum(closes[-50:]) / Decimal(50) if len(closes) >= 50 else None
    state = "insufficient_history"
    if sma20 is not None and sma50 is not None:
        state = (
            "sma20_above_sma50"
            if sma20 > sma50
            else ("sma20_below_sma50" if sma20 < sma50 else "moving_averages_equal")
        )
    result = TechnicalSummary(
        bars_used=len(closes),
        as_of=history.bars[-1].timestamp,
        sma20=sma20,
        sma50=sma50,
        state=state,
    )
    if len(closes) >= 15:
        changes = [b - a for a, b in pairwise(closes)]
        gain = sum(max(change, Decimal(0)) for change in changes[:14]) / 14
        loss = sum(max(-change, Decimal(0)) for change in changes[:14]) / 14
        for change in changes[14:]:
            gain = (gain * 13 + max(change, Decimal(0))) / 14
            loss = (loss * 13 + max(-change, Decimal(0))) / 14
        result.rsi14 = (
            Decimal(50)
            if not gain and not loss
            else Decimal(100)
            if not loss
            else 100 - 100 / (1 + gain / loss)
        )
    fast, slow = _ema(closes, 12), _ema(closes, 26)
    macd_values = [fast[index] - value for index, value in slow.items()]
    if macd_values:
        result.macd = macd_values[-1]
        signals = _ema(macd_values, 9)
        if signals:
            result.macd_signal = list(signals.values())[-1]
            result.macd_histogram = result.macd - result.macd_signal
    if sma20 is not None:
        deviation = (sum((value - sma20) ** 2 for value in closes[-20:]) / 20).sqrt()
        result.bollinger_upper = sma20 + 2 * deviation
        result.bollinger_lower = sma20 - 2 * deviation
    if len(closes) >= 21:
        result.return_20 = closes[-1] / closes[-21] - 1
        returns = [b / a - 1 for a, b in pairwise(closes[-21:])]
        mean = sum(returns) / 20
        variance = sum((value - mean) ** 2 for value in returns) / 19
        result.volatility_20_annualized = (variance * 252).sqrt()
    if len(closes) >= 2:
        peak = closes[0]
        worst = Decimal(0)
        for close in closes:
            peak = max(peak, close)
            worst = min(worst, close / peak - 1)
        result.max_drawdown = worst
        result.drawdown_from_peak = closes[-1] / peak - 1
    result.missing_indicators = [
        name
        for name in (
            "sma20",
            "sma50",
            "rsi14",
            "macd",
            "macd_signal",
            "macd_histogram",
            "bollinger_upper",
            "bollinger_lower",
            "return_20",
            "volatility_20_annualized",
            "max_drawdown",
            "drawdown_from_peak",
        )
        if getattr(result, name) is None
    ]
    return result


def _ema(values: list[Decimal], period: int) -> dict[int, Decimal]:
    """SMA seed at period-1; preserve indices for aligned MACD subtraction."""
    if len(values) < period:
        return {}
    value = sum(values[:period]) / period
    result = {period - 1: value}
    alpha = Decimal(2) / (period + 1)
    for index in range(period, len(values)):
        value = (values[index] - value) * alpha + value
        result[index] = value
    return result
