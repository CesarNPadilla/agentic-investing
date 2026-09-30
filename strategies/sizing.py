"""Provider-neutral sizing contract; no model confidence input."""

from decimal import ROUND_FLOOR, Decimal
from typing import Protocol

from portfolio.intelligence import experimental_utilization


class PositionSizer(Protocol):
    def quantity(
        self, *, notional: Decimal, price: Decimal, fees: Decimal, state, policy
    ) -> Decimal | None: ...


class FixedNotionalSizer:
    def quantity(self, *, notional, price, fees, state, policy):
        if (
            any(not v.is_finite() for v in (notional, price, fees))
            or price <= 0
            or fees < 0
            or notional <= 0
        ):
            return None
        sleeve = experimental_utilization(state, policy)
        limit = policy.agent_experimental_capital_limit
        if not sleeve.valid or limit is None:
            return None
        budget = min(notional, limit - sleeve.utilized - fees)
        quantity = (budget / price).to_integral_value(rounding=ROUND_FLOOR)
        return quantity if quantity > 0 else None
