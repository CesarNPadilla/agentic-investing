from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field

from market_data.models import Symbol


class Account(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    account_id: str
    currency: str = Field(pattern=r"^[A-Z]{3}$")


class Position(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    account_id: str
    symbol: Symbol
    quantity: Decimal = Field(allow_inf_nan=False)
    currency: str | None = Field(default=None, pattern=r"^[A-Z]{3}$")
    cost_basis: Decimal | None = Field(default=None, allow_inf_nan=False)
    market_value: Decimal | None = Field(default=None, allow_inf_nan=False)
    price: Decimal | None = Field(default=None, ge=0, allow_inf_nan=False)
    instrument_type: str | None = None


class CashBalance(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    account_id: str
    currency: str = Field(pattern=r"^[A-Z]{3}$")
    amount: Decimal = Field(allow_inf_nan=False)
    settled_cash: Decimal | None = Field(default=None, allow_inf_nan=False)
    unsettled_cash: Decimal | None = Field(default=None, allow_inf_nan=False)
    buying_power: Decimal | None = Field(default=None, allow_inf_nan=False)
