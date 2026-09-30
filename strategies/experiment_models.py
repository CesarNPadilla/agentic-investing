"""Explicit experimental rules, never inferred from external content or confidence."""

from decimal import Decimal
from typing import Literal

from pydantic import Field, model_validator

from market_data.models import Symbol
from portfolio.state import Identifier, Number, Record


class MetricRule(Record):
    name: Identifier
    dimension: Literal["fundamental_quality", "financial_health", "growth_durability", "valuation"]
    metric: Identifier
    unit: Identifier
    basis: Literal["quarter", "annual", "ttm", "point_in_time", "forward"]
    operator: Literal["ge", "le"]
    threshold: Number | None = None


class ExperimentParameters(Record):
    hypothesis: Literal["LONG_TERM_QUALITY_GROWTH", "SWING_TREND_MOMENTUM"]
    label: Literal["EXPERIMENTAL_NOT_PRODUCTION"] = "EXPERIMENTAL_NOT_PRODUCTION"
    permitted_symbols: tuple[Symbol, ...] = Field(min_length=1)
    metric_rules: tuple[MetricRule, ...] = ()
    trend_period: int = Field(default=200, ge=2)
    intermediate_period: int = Field(default=50, ge=2)
    rsi_period: int = Field(default=14, ge=2)
    rsi_lower: Decimal = Field(default=Decimal(50), ge=0, lt=100)
    rsi_upper: Decimal = Field(default=Decimal(75), gt=0, le=100)
    volume_period: int = Field(default=20, ge=2)
    require_volume: bool = True
    atr_period: int = Field(default=14, ge=2)
    atr_stop_multiple: Decimal | None = Field(default=None, gt=0, allow_inf_nan=False)
    max_holding_sessions: int | None = Field(default=None, gt=0)
    max_holding_days: int | None = Field(default=None, gt=0)
    parameters_approved_reference: Identifier | None = None

    @model_validator(mode="after")
    def valid(self):
        if self.intermediate_period >= self.trend_period or self.rsi_lower >= self.rsi_upper:
            raise ValueError("Experimental indicator periods/bounds are inconsistent")
        if len(set(self.permitted_symbols)) != len(self.permitted_symbols):
            raise ValueError("Duplicate experiment security")
        if len({r.name for r in self.metric_rules}) != len(self.metric_rules):
            raise ValueError("Duplicate metric rule")
        if self.hypothesis == "LONG_TERM_QUALITY_GROWTH" and not {
            "fundamental_quality",
            "financial_health",
            "growth_durability",
        } <= {r.dimension for r in self.metric_rules}:
            raise ValueError("Quality growth needs explicit fundamental, health and growth rules")
        return self


class DimensionCheck(Record):
    name: str
    dimension: str
    status: Literal["PASS", "FAIL", "UNSET", "INSUFFICIENT_DATA", "CONTEXT"]
    observed: str | None = None
    requirement: str
    evidence: tuple[str, ...] = ()
