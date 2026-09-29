"""Whole-portfolio analytics and explicitly attributed experimental capital."""

from decimal import Decimal
from typing import Literal

from pydantic import AwareDatetime, Field

from market_data.models import Symbol
from portfolio.state import PortfolioState, Record
from risk.policy import InvestmentPolicy

ZERO = Decimal(0)


class SecurityReference(Record):
    symbol: Symbol
    source: str = Field(min_length=1)
    as_of: AwareDatetime
    valid_until: AwareDatetime
    verified: bool = False
    security_type: Literal["individual_equity", "etf", "other", "unknown"] = "unknown"
    sector: str | None = None
    industry: str | None = None


class ExperimentalUtilization(Record):
    valid: bool
    reasons: tuple[str, ...]
    deployed_cost: Decimal | None = None
    open_commitments: Decimal | None = None
    utilized: Decimal | None = None
    remaining: Decimal | None = None
    utilization: Decimal | None = None


def experimental_utilization(state: PortfolioState, policy: InvestmentPolicy):
    attribution = state.experimental_attribution
    reasons = []
    if attribution is None:
        return ExperimentalUtilization(valid=False, reasons=("experimental_attribution_unset",))
    if not attribution.complete or attribution.as_of != state.as_of:
        reasons.append("experimental_attribution_incomplete_or_stale")
    if not all((state.accounts_complete, state.positions_complete, state.orders_complete)):
        reasons.append("experimental_broker_inventory_incomplete")
    if any(a.currency != "USD" for a in state.accounts) or any(
        p.currency != "USD" for p in state.positions):
        reasons.append("unsupported_experimental_currency")
    accounts = {a.account_id for a in state.accounts}
    if (
        not attribution.account_ids
        or len(set(attribution.account_ids)) != len(attribution.account_ids)
        or not set(attribution.account_ids) <= accounts
    ):
        reasons.append("invalid_experimental_accounts")
    positions = {(p.account_id, p.symbol): p for p in state.positions}
    orders = {(o.account_id, o.order_id): o for o in state.open_orders}
    if len(positions) != len(state.positions) or len(orders) != len(state.open_orders):
        reasons.append("duplicate_broker_inventory")
    used, reserved = ZERO, ZERO
    seen = set()
    for allocation in attribution.positions:
        key = (allocation.account_id, allocation.symbol)
        actual = positions.get(key)
        if (
            key in seen
            or actual is None
            or allocation.account_id not in attribution.account_ids
            or actual.quantity < allocation.quantity
            or actual.quantity < 0
            or (allocation.quantity == 0 and allocation.cost_basis != 0)
            or (actual.cost_basis is not None and allocation.cost_basis > actual.cost_basis)
            or (actual.cost_basis is not None and allocation.quantity == actual.quantity
                and allocation.cost_basis != actual.cost_basis)
        ):
            reasons.append("invalid_experimental_position")
        seen.add(key)
        used += allocation.cost_basis
    seen = set()
    for allocation in attribution.open_orders:
        key = (allocation.account_id, allocation.order_id)
        actual = orders.get(key)
        if key in seen or actual is None or allocation.account_id not in attribution.account_ids:
            reasons.append("invalid_experimental_order")
        elif (
            actual.side != "buy"
            or actual.limit_price is None
            or actual.remaining_fees is None
            or actual.status == "unknown"
            or actual.complex
        ):
            reasons.append("unknown_experimental_commitment")
        else:
            reserved += (
                actual.quantity - actual.filled_quantity
            ) * actual.limit_price + actual.remaining_fees
        seen.add(key)
    if reasons:
        return ExperimentalUtilization(valid=False, reasons=tuple(sorted(set(reasons))))
    limit = policy.agent_experimental_capital_limit
    utilized = used + reserved
    return ExperimentalUtilization(
        valid=True,
        reasons=(),
        deployed_cost=used,
        open_commitments=reserved,
        utilized=utilized,
        remaining=limit - utilized if limit is not None else None,
        utilization=utilized / limit if limit else None,
    )


class SecurityAllocation(Record):
    symbol: Symbol
    market_value: Decimal
    allocation: Decimal | None
    concentration: Decimal | None
    warning: Literal["concentration", "severe_concentration"] | None = None


class PortfolioIntelligence(Record):
    total_position_market_value: Decimal | None
    total_portfolio_market_value: Decimal | None
    total_cost_basis: Decimal | None
    unrealized_pnl: Decimal | None
    cash: Decimal | None
    cash_allocation: Decimal | None
    allocation_by_security: tuple[SecurityAllocation, ...]
    top_concentrations: tuple[SecurityAllocation, ...]
    exposure_by_security_type: dict[str, Decimal]
    sector_exposure: dict[str, Decimal]
    industry_exposure: dict[str, Decimal]
    experimental_capital: ExperimentalUtilization
    data_gaps: tuple[str, ...]


def analyze_portfolio(
    state: PortfolioState, policy: InvestmentPolicy, references: tuple[SecurityReference, ...] = ()
) -> PortfolioIntelligence:
    gaps = list(state.data_gaps)
    unique = len({(p.account_id, p.symbol) for p in state.positions}) == len(state.positions)
    accounts = {a.account_id: a for a in state.accounts}
    scope_ok = (
        len(accounts) == len(state.accounts)
        and bool(accounts)
        and all(p.account_id in accounts for p in state.positions)
    )
    usd = all(a.currency == "USD" for a in state.accounts) and all(
        p.currency == "USD" for p in state.positions
    )
    complete = state.accounts_complete and state.positions_complete and unique and scope_ok and usd
    if not complete:
        gaps.append("incomplete_or_unsupported_portfolio_scope")
    valued = complete and all(p.marked_value is not None for p in state.positions)
    position_value = sum((p.marked_value for p in state.positions), ZERO) if valued else None
    cash = (
        sum((a.cash for a in state.accounts), ZERO)
        if complete and all(a.cash is not None for a in state.accounts)
        else None
    )
    total = position_value + cash if position_value is not None and cash is not None else None
    basis = (
        sum((p.cost_basis for p in state.positions), ZERO)
        if complete and all(p.cost_basis is not None and p.quantity >= 0 for p in state.positions)
        else None
    )
    if position_value is None:
        gaps.append("market_value_unavailable")
    if basis is None:
        gaps.append("cost_basis_unavailable")
    if total is None or total <= 0:
        gaps.append("allocation_unavailable")
    reference_map = {}
    duplicates = set()
    for ref in references:
        if ref.symbol in reference_map:
            duplicates.add(ref.symbol)
        reference_map[ref.symbol] = ref
    values, gross, types, sectors, industries = {}, {}, {}, {}, {}
    if valued:
        for position in state.positions:
            value = position.marked_value
            symbol = position.symbol
            values[symbol] = values.get(symbol, ZERO) + value
            gross[symbol] = gross.get(symbol, ZERO) + abs(value)
            ref = reference_map.get(symbol)
            reliable = (
                ref is not None
                and symbol not in duplicates
                and ref.verified
                and ref.as_of <= state.as_of <= ref.valid_until
            )
            security_type = ref.security_type if reliable else "unknown"
            # Fund look-through is not inferred from an ETF's issuer classification.
            sector = ref.sector if reliable and security_type == "individual_equity" else None
            industry = ref.industry if reliable and security_type == "individual_equity" else None
            for group, key in (
                (types, security_type),
                (sectors, sector or "unknown"),
                (industries, industry or "unknown"),
            ):
                group[key] = group.get(key, ZERO) + abs(value)
            if not reliable:
                gaps.append("reference_data_unavailable:" + symbol)
    rows = []
    for symbol in sorted(values):
        weight = gross[symbol] / total if total is not None and total > 0 else None
        warning = None
        if weight is not None:
            if weight > policy.severe_concentration_warning:
                warning = "severe_concentration"
            elif weight > policy.concentration_warning:
                warning = "concentration"
        rows.append(
            SecurityAllocation(
                symbol=symbol,
                market_value=values[symbol],
                allocation=values[symbol] / total if total is not None and total > 0 else None,
                concentration=weight,
                warning=warning,
            )
        )
    return PortfolioIntelligence(
        total_position_market_value=position_value,
        total_portfolio_market_value=total,
        total_cost_basis=basis,
        unrealized_pnl=position_value - basis
        if position_value is not None and basis is not None
        else None,
        cash=cash,
        cash_allocation=cash / total if total is not None and total > 0 else None,
        allocation_by_security=tuple(rows),
        top_concentrations=tuple(sorted(rows, key=lambda r: (-gross[r.symbol], r.symbol))[:10]),
        exposure_by_security_type=types,
        sector_exposure=sectors,
        industry_exposure=industries,
        experimental_capital=experimental_utilization(state, policy),
        data_gaps=tuple(sorted(set(gaps))),
    )
