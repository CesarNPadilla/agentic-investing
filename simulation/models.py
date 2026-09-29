from datetime import UTC, datetime
from decimal import Decimal
from typing import Literal
from uuid import UUID, uuid4
from zoneinfo import ZoneInfo

from pydantic import BaseModel, ConfigDict, Field, model_validator

from technical.history import DailyClose, HistoryEvidence


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class Strategy(StrictModel):
    name: Literal["buy_and_hold", "sma"] = "sma"
    version: Literal["1"] = "1"
    fast: int = Field(default=20, ge=1, le=499)
    slow: int = Field(default=50, ge=2, le=500)

    @model_validator(mode="after")
    def windows(self):
        if self.fast >= self.slow:
            raise ValueError("fast must be smaller than slow")
        return self


class SimulationInput(StrictModel):
    strategy: Strategy = Field(default_factory=Strategy)
    history: HistoryEvidence
    benchmark: HistoryEvidence
    initial_cash: Decimal = Field(default=Decimal(10000), gt=0, allow_inf_nan=False)
    fee_bps: Decimal = Field(default=Decimal(0), ge=0, le=100, allow_inf_nan=False)
    slippage_bps: Decimal = Field(default=Decimal(0), ge=0, le=100, allow_inf_nan=False)
    currency: Literal["USD"] = "USD"

    @model_validator(mode="after")
    def aligned(self):
        times = [b.timestamp for b in self.history.bars]
        if not times or times != [b.timestamp for b in self.benchmark.bars]:
            raise ValueError("Nonempty strategy and benchmark histories must align exactly")
        today = datetime.now(ZoneInfo("America/New_York")).date()
        if any(t.astimezone(ZoneInfo("America/New_York")).date() >= today for t in times):
            raise ValueError("Only completed prior New York calendar days are accepted")
        if self.history.adjustment != self.benchmark.adjustment:
            raise ValueError("Strategy and benchmark adjustment conventions must match")
        return self


class PaperAdvance(StrictModel):
    expected_revision: int = Field(ge=0)
    bar: DailyClose
    benchmark_bar: DailyClose


class SimulationRun(StrictModel):
    id: UUID = Field(default_factory=uuid4)
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    engine_version: Literal["simulation-v1"] = "simulation-v1"
    mode: Literal["backtest", "paper"]
    revision: int = 0
    inputs: SimulationInput
    dataset_hash: str
    metrics: dict
    equity_curve: list[dict]
    decisions: list[dict]
    fills: list[dict]
    closed_trades: list[dict]
    warnings: list[str]
