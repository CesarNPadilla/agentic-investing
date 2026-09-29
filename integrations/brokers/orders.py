"""Order-submission contract only; no network execution adapter is provided."""

from decimal import Decimal
from typing import Literal, Protocol
from uuid import UUID

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field

from market_data.models import Symbol


class LimitOrder(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    account_id: str = Field(min_length=1, max_length=100)
    client_order_id: UUID
    symbol: Symbol
    side: Literal["buy", "sell"]
    quantity: Decimal = Field(gt=0, max_digits=12, decimal_places=6, allow_inf_nan=False)
    limit_price: Decimal = Field(gt=0, max_digits=12, decimal_places=2, allow_inf_nan=False)
    order_type: Literal["limit"] = "limit"
    time_in_force: Literal["day"] = "day"


class OrderReceipt(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    client_order_id: UUID
    broker_order_id: str | None = None
    status: Literal["accepted", "partially_filled", "filled", "canceled", "rejected", "unknown"]
    filled_quantity: Decimal = Field(default=Decimal(0), ge=0, allow_inf_nan=False)
    average_fill_price: Decimal | None = Field(default=None, gt=0, allow_inf_nan=False)
    updated_at: AwareDatetime


class OrderExecutionAdapter(Protocol):
    """Idempotent adapter boundary; callers must reconcile unknown outcomes."""

    def submit_limit_order(self, order: LimitOrder) -> OrderReceipt: ...
    def get_order(self, client_order_id: UUID) -> OrderReceipt | None: ...
    def cancel_order(self, client_order_id: UUID) -> OrderReceipt: ...