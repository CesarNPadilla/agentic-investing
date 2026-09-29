"""Read-only exposure from a caller-valued single-currency equity snapshot."""

from datetime import datetime
from decimal import Decimal
from typing import Literal

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, model_validator

from market_data.models import Symbol


class Holding(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    account_id: str = Field(min_length=1, max_length=100)
    symbol: Symbol
    asset_type: Literal["equity"] = "equity"
    quantity: Decimal = Field(allow_inf_nan=False)
    price: Decimal = Field(gt=0, allow_inf_nan=False)
    price_as_of: AwareDatetime
    price_source: str = Field(min_length=1, max_length=200)
    currency: str = Field(pattern=r"^[A-Z]{3}$")
    sector: str | None = Field(default=None, min_length=1, max_length=100)


class SnapshotCash(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    account_id: str = Field(min_length=1, max_length=100)
    currency: str = Field(pattern=r"^[A-Z]{3}$")
    amount: Decimal = Field(allow_inf_nan=False)


class PortfolioSnapshot(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    source: str = Field(min_length=1, max_length=200)
    as_of: AwareDatetime
    currency: str = Field(pattern=r"^[A-Z]{3}$")
    is_sample: bool = False
    holdings: tuple[Holding, ...] = Field(max_length=1000)
    cash: tuple[SnapshotCash, ...] = Field(max_length=1000)

    @model_validator(mode="after")
    def consistent_snapshot(self):
        keys = [(row.account_id, row.symbol) for row in self.holdings]
        if len(keys) != len(set(keys)):
            raise ValueError("Consolidate duplicate account/symbol holdings before import")
        cash_keys = [row.account_id for row in self.cash]
        if len(cash_keys) != len(set(cash_keys)):
            raise ValueError("Only one cash balance per account is allowed")
        if any(row.currency != self.currency for row in (*self.holdings, *self.cash)):
            raise ValueError(
                "All positions and cash must use the snapshot currency; FX unsupported"
            )
        if any(row.price_as_of > self.as_of for row in self.holdings):
            raise ValueError("Position prices must not postdate the snapshot")
        sectors = {}
        for row in self.holdings:
            if row.symbol in sectors and sectors[row.symbol] != row.sector:
                raise ValueError("Sector classification must agree across accounts for a symbol")
            sectors[row.symbol] = row.sector
        return self


class Exposure(BaseModel):
    net_value: Decimal
    gross_value: Decimal
    net_weight: Decimal | None = None
    gross_weight: Decimal | None = None


class PortfolioExposure(BaseModel):
    model_config = ConfigDict(extra="forbid")
    evidence: PortfolioSnapshot
    state: Literal["available", "unavailable"] = "available"
    equity: Decimal | None = None
    cash_value: Decimal | None = None
    long_value: Decimal | None = None
    short_value: Decimal | None = None
    gross_exposure: Decimal | None = None
    net_exposure: Decimal | None = None
    gross_leverage: Decimal | None = None
    net_leverage: Decimal | None = None
    cash_weight: Decimal | None = None
    by_symbol: dict[str, Exposure] = Field(default_factory=dict)
    by_sector: dict[str, Exposure] = Field(default_factory=dict)
    by_account: dict[str, Exposure] = Field(default_factory=dict)
    researched_symbol: Symbol
    researched_symbol_exposure: Exposure | None = None
    warnings: list[str] = Field(default_factory=list)


def analyze(snapshot: PortfolioSnapshot, symbol: str, now: datetime) -> PortfolioExposure:
    result = PortfolioExposure(evidence=snapshot, researched_symbol=symbol)
    if snapshot.as_of > now:
        result.state = "unavailable"
        result.warnings.append("Portfolio snapshot is future-dated; exposure omitted.")
        return result
    values = [(row, row.quantity * row.price) for row in snapshot.holdings]
    result.cash_value = sum((row.amount for row in snapshot.cash), Decimal(0))
    result.long_value = sum((max(value, Decimal(0)) for _, value in values), Decimal(0))
    result.short_value = sum((max(-value, Decimal(0)) for _, value in values), Decimal(0))
    result.gross_exposure = result.long_value + result.short_value
    result.net_exposure = result.long_value - result.short_value
    result.equity = result.net_exposure + result.cash_value
    if result.equity > 0:
        result.gross_leverage = result.gross_exposure / result.equity
        result.net_leverage = result.net_exposure / result.equity
        result.cash_weight = result.cash_value / result.equity
    else:
        result.warnings.append("Portfolio equity is nonpositive; all equity-based weights omitted.")
    for row, value in values:
        for groups, key in (
            (result.by_symbol, row.symbol),
            (result.by_sector, row.sector or "Unknown"),
            (result.by_account, row.account_id),
        ):
            item = groups.setdefault(key, Exposure(net_value=0, gross_value=0))
            item.net_value += value
            item.gross_value += abs(value)
    for groups in (result.by_symbol, result.by_sector, result.by_account):
        for item in groups.values():
            if result.equity > 0:
                item.net_weight = item.net_value / result.equity
                item.gross_weight = item.gross_value / result.equity
    result.researched_symbol_exposure = result.by_symbol.get(
        symbol,
        Exposure(
            net_value=0,
            gross_value=0,
            net_weight=Decimal(0) if result.equity > 0 else None,
            gross_weight=Decimal(0) if result.equity > 0 else None,
        ),
    )
    if (now - snapshot.as_of).total_seconds() > 86400:
        result.warnings.append("Portfolio snapshot is over 24 hours old.")
    if any((now - row.price_as_of).total_seconds() > 86400 for row in snapshot.holdings):
        result.warnings.append("One or more position prices are over 24 hours old.")
    if any(row.sector is None and row.quantity != 0 for row in snapshot.holdings):
        result.warnings.append(
            "Some holdings lack sector classifications; Unknown exposure retained."
        )
    if snapshot.is_sample:
        result.warnings.append("Synthetic portfolio snapshot; not actual account exposure.")
    result.warnings.append(
        "Exposure covers only supplied equity positions and cash; import completeness is unverified."
    )
    return result
