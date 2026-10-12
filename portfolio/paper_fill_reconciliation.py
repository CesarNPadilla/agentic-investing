"""Strict whole-share FILL replay with explicit unknown fee/settlement blockers."""

from decimal import Decimal
from typing import Literal

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, model_validator

from market_data.models import Symbol


class PaperFill(BaseModel):
    model_config = ConfigDict(frozen=True, extra="ignore")
    activity_type: Literal["FILL"]
    id: str = Field(min_length=1)
    order_id: str = Field(min_length=1)
    symbol: Symbol
    side: Literal["buy", "sell"]
    qty: Decimal = Field(gt=0, allow_inf_nan=False)
    price: Decimal = Field(gt=0, allow_inf_nan=False)
    cum_qty: Decimal = Field(gt=0, allow_inf_nan=False)
    leaves_qty: Decimal = Field(ge=0, allow_inf_nan=False)
    transaction_time: AwareDatetime

    @model_validator(mode="after")
    def whole_shares(self):
        if any(x != x.to_integral_value() for x in (self.qty, self.cum_qty, self.leaves_qty)):
            raise ValueError("Plumbing strategy requires whole shares")
        if self.qty > self.cum_qty:
            raise ValueError("Fill exceeds cumulative quantity")
        return self


def reconcile_fills(batch, *, opening_cash, opening_positions, closing_cash, closing_positions):
    amounts = [Decimal(str(x)) for x in (opening_cash, closing_cash)]
    if any(not x.is_finite() for x in amounts):
        raise ValueError("Finite cash required")

    def positions(values):
        result = {k: Decimal(str(v)) for k, v in values.items()}
        if any(not v.is_finite() or v < 0 or v != v.to_integral_value() for v in result.values()):
            raise ValueError("Whole-share long positions required")
        return {k: v for k, v in result.items() if v}

    expected = positions(opening_positions)
    closing = positions(closing_positions)
    cash = amounts[0]
    reasons = {"FEES_AND_EXTERNAL_FLOWS_UNRECONCILED", "SETTLED_CASH_UNVERIFIED"}
    if not batch.pagination_exhausted:
        reasons.add("ACTIVITY_COVERAGE_INCOMPLETE")
    ids, orders = set(), {}
    fills = []
    for row in batch.rows:
        if row.get("activity_type") != "FILL":
            reasons.add("NONFILL_ACTIVITY_REQUIRES_MAPPING")
            continue
        fill = PaperFill.model_validate(row)
        if fill.id in ids:
            raise ValueError("Duplicate activity")
        ids.add(fill.id)
        if not batch.after < fill.transaction_time <= batch.until:
            reasons.add("FILL_OUTSIDE_REPLAY_INTERVAL")
            continue
        fills.append(fill)
    # Preserve provider order at equal event times; reject ambiguous cumulative sequencing.
    for fill in sorted(fills, key=lambda x: x.transaction_time):
        old = orders.get(fill.order_id)
        total = (old[2] if old else Decimal(0)) + fill.qty
        if old and old[:2] != (fill.symbol, fill.side):
            raise ValueError("Order identity changed")
        if fill.cum_qty != total:
            reasons.add("ORDER_FILL_HISTORY_INCOMPLETE")
        orders[fill.order_id] = (fill.symbol, fill.side, total)
        sign = Decimal(1) if fill.side == "buy" else Decimal(-1)
        expected[fill.symbol] = expected.get(fill.symbol, Decimal(0)) + sign * fill.qty
        cash -= sign * fill.qty * fill.price
        if expected[fill.symbol] < 0:
            reasons.add("UNEXPLAINED_SHORT_POSITION")
    expected = {k: v for k, v in expected.items() if v}
    if expected != closing:
        reasons.add("POSITION_LEDGER_MISMATCH")
    if cash != amounts[1]:
        reasons.add("CASH_LEDGER_MISMATCH")
    return {
        "fill_count": len(fills),
        "position_ledger_matches": expected == closing,
        "trade_cash_matches": cash == amounts[1],
        "blockers": sorted(reasons),
        "execution_available": False,
        "settlement_verified": False,
    }
