from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class RiskPolicy(BaseModel):
    """Versioned research heuristics, not personalized limits or execution controls."""

    model_config = ConfigDict(extra="forbid", frozen=True)
    version: Literal["research-v1"] = "research-v1"
    symbol_concentration: Decimal = Decimal("0.25")
    sector_concentration: Decimal = Decimal("0.40")
    gross_leverage: Decimal = Decimal(1)
    annualized_volatility: Decimal = Decimal("0.40")
    drawdown: Decimal = Decimal("-0.20")
    debt_to_equity: Decimal = Decimal(2)
    current_ratio: Decimal = Decimal(1)
    catalyst_horizon_days: int = 7


class RiskFinding(BaseModel):
    model_config = ConfigDict(extra="forbid")
    code: str
    category: Literal["data_quality", "technical", "fundamental", "portfolio", "event"]
    severity: Literal["info", "medium", "high"]
    message: str
    evidence_refs: list[str] = Field(default_factory=list)
    observed: Decimal | None = None
    threshold: Decimal | None = None
