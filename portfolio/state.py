"""Complete, broker-neutral read contract; unknown values are never synthesized."""

from decimal import Decimal
from typing import Annotated, Literal

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, model_validator

from market_data.models import Symbol

Number = Annotated[Decimal, Field(allow_inf_nan=False)]
Nonnegative = Annotated[Decimal, Field(ge=0, allow_inf_nan=False)]
Identifier = Annotated[str, Field(min_length=1)]


class Record(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


class StateAccount(Record):
    account_id: Identifier
    currency: str = Field(pattern=r"^[A-Z]{3}$")
    account_type: Literal["cash", "margin", "unknown"] = "unknown"
    cash: Number | None = None
    settled_cash: Number | None = None
    unsettled_cash: Number | None = None
    buying_power: Nonnegative | None = None
    broker_market_value: Number | None = None
    broker_equity: Number | None = None
    # Gross ledger cash, before open-order reservations; unknown semantics block evaluation.
    cash_basis: Literal["before_reservations", "unknown"] = "unknown"


class StatePosition(Record):
    account_id: Identifier
    symbol: Symbol
    quantity: Number
    price: Annotated[Decimal, Field(gt=0, allow_inf_nan=False)] | None = None
    cost_basis: Nonnegative | None = None
    price_as_of: AwareDatetime | None = None
    asset_type: Literal["equity", "option", "unknown"] = "unknown"
    leverage_factor: Nonnegative | None = None
    currency: str = Field(default="USD", pattern=r"^[A-Z]{3}$")
    market_value: Number | None = None
    broker_unrealized_pnl: Number | None = None
    observed_at: AwareDatetime | None = None

    @property
    def marked_value(self):
        if self.market_value is not None:
            return self.market_value
        if self.asset_type == "equity" and self.price is not None:
            return self.quantity * self.price
        return None


class StateOrder(Record):
    account_id: Identifier
    order_id: Identifier
    symbol: Symbol
    side: Literal["buy", "sell", "short"]
    quantity: Annotated[Decimal, Field(gt=0, allow_inf_nan=False)]
    filled_quantity: Nonnegative
    limit_price: Nonnegative | None = None
    remaining_fees: Nonnegative | None = None
    status: Literal["open", "partially_filled", "pending_cancel", "unknown"]
    asset_type: Literal["equity", "option", "unknown"] = "unknown"
    leverage_factor: Nonnegative | None = None
    order_type: str = "unknown"
    time_in_force: str = "unknown"
    session: str = "unknown"
    complex: bool = True

    @model_validator(mode="after")
    def valid_fill(self):
        if self.filled_quantity > self.quantity:
            raise ValueError("Filled quantity exceeds total quantity")
        return self


class Transaction(Record):
    """Signed, posted ledger movements, including explicit settlement transfers.

    Corrections must be new reversal/replacement events, never overwritten IDs.
    Broker adapters must include fees in cash_delta and provide settlement deltas.
    """

    account_id: Identifier
    transaction_id: Identifier
    posted_at: AwareDatetime
    currency: str = Field(pattern=r"^[A-Z]{3}$")
    kind: Literal[
        "fill", "fee", "deposit", "withdrawal", "settlement", "adjustment", "broker_activity"
    ]
    symbol: Symbol | None = None
    quantity_delta: Number | None = Decimal(0)
    cash_delta: Number
    settled_delta: Number | None = None
    unsettled_delta: Number | None = None
    activity_type: str | None = None
    activity_sub_type: str | None = None

    @model_validator(mode="after")
    def valid_deltas(self):
        if self.quantity_delta and self.symbol is None:
            raise ValueError("Position movement requires a symbol")
        if (
            self.settled_delta is not None
            and self.unsettled_delta is not None
            and self.cash_delta != self.settled_delta + self.unsettled_delta
        ):
            raise ValueError("Cash movement differs from settlement components")
        return self


class ExperimentalPosition(Record):
    account_id: Identifier
    symbol: Symbol
    quantity: Nonnegative
    cost_basis: Nonnegative
    strategy_id: str | None = None
    strategy_domain: Literal["long_term", "swing"] | None = None


class ExperimentalOrder(Record):
    account_id: Identifier
    order_id: Identifier
    strategy_id: str | None = None


class ExperimentalAttribution(Record):
    """Explicit reviewed sleeve inventory, never inferred from symbol or account size."""

    baseline_id: Identifier
    source: Identifier
    as_of: AwareDatetime
    complete: bool = False
    account_ids: tuple[Identifier, ...]
    positions: tuple[ExperimentalPosition, ...]
    open_orders: tuple[ExperimentalOrder, ...]
    realized_pnl: Number | None = None


class PortfolioState(Record):
    model_config = ConfigDict(frozen=True, extra="forbid", populate_by_name=True)
    schema_version: Literal["portfolio-state-v2"] = "portfolio-state-v2"
    source: Identifier
    environment: Literal["research", "paper", "production"]
    as_of: AwareDatetime
    # All collections must represent the same cutoff, with every page consumed.
    accounts_complete: bool = False
    positions_complete: bool = False
    orders_complete: bool = False
    transactions_complete: bool = False
    history_start: AwareDatetime
    accounts: tuple[StateAccount, ...]
    positions: tuple[StatePosition, ...] = Field(alias="portfolio_holdings")
    open_orders: tuple[StateOrder, ...]
    transactions: tuple[Transaction, ...]
    experimental_attribution: ExperimentalAttribution | None = None
    coherent_cutoff: bool = True
    read_started_at: AwareDatetime | None = None
    data_gaps: tuple[str, ...] = ()
    # Flow-adjusted account-wide realized + unrealized P&L; never inferred from cash.
    daily_pnl: Number | None = None
    experimental_pnl: Number | None = None
    experimental_strategy_pnl: dict[str, Number] | None = None
    realized_pnl: Number | None = None
    daily_pnl_start: AwareDatetime | None = None
    daily_pnl_as_of: AwareDatetime | None = None

    @property
    def portfolio_holdings(self) -> tuple[StatePosition, ...]:
        """All broker positions, independent of research/purchase permissions."""
        return self.positions


class Reconciliation(Record):
    version: Literal["reconciliation-v1"] = "reconciliation-v1"
    passed: bool
    reasons: tuple[str, ...]
    gross_exposure: Decimal | None
    per_position: dict[str, Decimal]
    per_symbol: dict[str, Decimal]
    cash: Decimal | None
    settled_cash: Decimal | None
    unsettled_cash: Decimal | None
    buying_power: Decimal | None
    equity: Decimal | None
    cash_allocation: Decimal | None
    concentration: Decimal | None
    open_buy_commitment: Decimal | None
