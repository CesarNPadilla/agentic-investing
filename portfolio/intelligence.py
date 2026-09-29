"""Whole-portfolio analytics and explicitly attributed experimental capital."""

from decimal import Decimal
from typing import Literal

from pydantic import AwareDatetime, Field

from market_data.models import Symbol
from portfolio.performance import PerformanceEvidence, PortfolioPerformance, performance
from portfolio.registry import initial_thesis
from portfolio.state import PortfolioState, Record
from portfolio.theses import PositionThesis
from risk.policy import MAGNIFICENT_SEVEN, InvestmentPolicy

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
    market_cap_bucket: Literal["mega", "large", "mid", "small", "micro", "unknown"] = "unknown"
    themes: tuple[str, ...] = ()


class CorrelationEvidence(Record):
    symbol_a: Symbol
    symbol_b: Symbol
    correlation: Decimal = Field(ge=-1, le=1, allow_inf_nan=False)
    observations: int = Field(ge=2)
    source: str = Field(min_length=1)
    window_start: AwareDatetime
    window_end: AwareDatetime
    valid_until: AwareDatetime
    verified: bool = False


class ExperimentalUtilization(Record):
    valid: bool
    reasons: tuple[str, ...]
    deployed_cost: Decimal | None = None
    open_commitments: Decimal | None = None
    utilized: Decimal | None = None
    remaining: Decimal | None = None
    utilization: Decimal | None = None
    realized_pnl: Decimal | None = None
    unrealized_pnl: Decimal | None = None
    strategy_attribution: dict[str, Decimal] = Field(default_factory=dict)


class CorrelatedExposure(Record):
    symbols: tuple[Symbol, Symbol]
    correlation: Decimal
    combined_gross_exposure: Decimal
    observations: int
    source: str
    window_start: AwareDatetime
    window_end: AwareDatetime


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
        p.currency != "USD" for p in state.positions
    ):
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
            or (
                actual.cost_basis is not None
                and allocation.quantity == actual.quantity
                and allocation.cost_basis != actual.cost_basis
            )
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
    unrealized = ZERO
    strategies = {}
    for allocation in attribution.positions:
        actual = positions[(allocation.account_id, allocation.symbol)]
        if actual.marked_value is None:
            unrealized = None
        elif unrealized is not None and allocation.quantity:
            unrealized += (
                actual.marked_value * allocation.quantity / actual.quantity - allocation.cost_basis
            )
        strategy = allocation.strategy_id or "unknown"
        strategies[strategy] = strategies.get(strategy, ZERO) + allocation.cost_basis
    for allocation in attribution.open_orders:
        actual = orders[(allocation.account_id, allocation.order_id)]
        strategy = allocation.strategy_id or "unknown"
        strategies[strategy] = (
            strategies.get(strategy, ZERO)
            + (actual.quantity - actual.filled_quantity) * actual.limit_price
            + actual.remaining_fees
        )
    return ExperimentalUtilization(
        valid=True,
        reasons=(),
        deployed_cost=used,
        open_commitments=reserved,
        utilized=utilized,
        remaining=limit - utilized if limit is not None else None,
        utilization=utilized / limit if limit else None,
        realized_pnl=attribution.realized_pnl,
        unrealized_pnl=unrealized,
        strategy_attribution=strategies,
    )


class SecurityAllocation(Record):
    symbol: Symbol
    market_value: Decimal
    allocation: Decimal | None
    concentration: Decimal | None
    warning: Literal["concentration", "severe_concentration"] | None = None


class PortfolioIntelligence(Record):
    as_of: AwareDatetime
    total_position_market_value: Decimal | None
    total_portfolio_market_value: Decimal | None
    total_cost_basis: Decimal | None
    unrealized_pnl: Decimal | None
    cash: Decimal | None
    cash_allocation: Decimal | None
    settled_cash: Decimal | None
    unsettled_cash: Decimal | None
    buying_power: Decimal | None
    realized_pnl: Decimal | None
    allocation_by_security: tuple[SecurityAllocation, ...]
    top_concentrations: tuple[SecurityAllocation, ...]
    exposure_by_security_type: dict[str, Decimal]
    sector_exposure: dict[str, Decimal]
    industry_exposure: dict[str, Decimal]
    market_cap_exposure: dict[str, Decimal]
    magnificent_seven_exposure: Decimal | None
    technology_exposure: Decimal | None
    speculative_exposure: Decimal | None
    crypto_related_exposure: Decimal | None
    swing_exposure: Decimal | None
    swing_eligible_exposure: Decimal | None
    thematic_exposure: dict[str, Decimal]
    sleeve_exposure: dict[str, Decimal]
    sleeve_monitoring: dict[str, str]
    correlated_exposure: tuple[CorrelatedExposure, ...] | None = None
    performance: PortfolioPerformance
    experimental_capital: ExperimentalUtilization
    data_gaps: tuple[str, ...]


def analyze_portfolio(
    state: PortfolioState,
    policy: InvestmentPolicy,
    references: tuple[SecurityReference, ...] = (),
    theses: tuple[PositionThesis, ...] = (),
    correlations: tuple[CorrelationEvidence, ...] = (),
    performance_evidence: PerformanceEvidence | None = None,
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
    values, gross, types, sectors, industries, caps, themes, sleeves = (
        {},
        {},
        {},
        {},
        {},
        {},
        {},
        {},
    )
    thesis_map = {(t.account_id, t.symbol): t for t in theses}
    if len(thesis_map) != len(theses):
        raise ValueError("Duplicate position thesis")
    speculative, crypto, swing, eligible = ZERO, ZERO, ZERO, ZERO
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
            cap = ref.market_cap_bucket if reliable else "unknown"
            # Fund look-through is not inferred from an ETF's issuer classification.
            sector = ref.sector if reliable and security_type == "individual_equity" else None
            industry = ref.industry if reliable and security_type == "individual_equity" else None
            for group, key in (
                (types, security_type),
                (sectors, sector or "unknown"),
                (industries, industry or "unknown"),
                (caps, cap),
            ):
                group[key] = group.get(key, ZERO) + abs(value)
            if not reliable:
                gaps.append("reference_data_unavailable:" + symbol)
                gaps.append("thematic_exposure_partial")
            thesis = thesis_map.get((position.account_id, symbol)) or initial_thesis(
                position.account_id, symbol
            )
            if thesis.classification == "UNCLASSIFIED":
                gaps.append("speculative_classification_incomplete:" + symbol)
            sleeve = thesis.sleeve or "UNASSIGNED"
            sleeves[sleeve] = sleeves.get(sleeve, ZERO) + abs(value)
            if thesis.classification.startswith("SPECULATIVE"):
                speculative += abs(value)
            if symbol in {"COIN", "RIOT"} or (reliable and "crypto_related" in ref.themes):
                crypto += abs(value)
            elif not reliable:
                gaps.append("crypto_related_exposure_partial")
            if thesis.strategy_domain == "swing" and swing is not None:
                swing += abs(value)
            elif thesis.strategy_domain is None:
                swing = None
            if "SWING_ELIGIBLE" in thesis.secondary_classifications:
                eligible += abs(value)
            for theme in ref.themes if reliable else ():
                themes[theme] = themes.get(theme, ZERO) + abs(value)
    if cash is not None:
        sleeves["CASH"] = cash
    monitoring = {}
    for key, band in (
        ("CORE", policy.core_monitoring_range),
        ("STRATEGIC", policy.strategic_monitoring_range),
        ("SATELLITE", policy.satellite_monitoring_range),
    ):
        weight = (
            sleeves.get(key, ZERO) / total if valued and total is not None and total > 0 else None
        )
        monitoring[key] = (
            "INSUFFICIENT_DATA"
            if weight is None or sleeves.get("UNASSIGNED", ZERO)
            else "BELOW_MONITORING_RANGE"
            if weight < band.minimum
            else "ABOVE_MONITORING_RANGE"
            if weight > band.maximum
            else "IN_MONITORING_RANGE"
        )
    pairs, seen_pairs = [], set()
    pair_keys = [tuple(sorted((c.symbol_a, c.symbol_b))) for c in correlations]
    for evidence in correlations:
        key = tuple(sorted((evidence.symbol_a, evidence.symbol_b)))
        if (
            not evidence.verified
            or evidence.symbol_a == evidence.symbol_b
            or pair_keys.count(key) > 1
            or key in seen_pairs
            or not evidence.window_start
            < evidence.window_end
            <= state.as_of
            <= evidence.valid_until
            or not all(symbol in gross for symbol in key)
        ):
            gaps.append("correlation_evidence_unavailable")
            continue
        seen_pairs.add(key)
        pairs.append(
            CorrelatedExposure(
                symbols=key,
                correlation=evidence.correlation,
                combined_gross_exposure=sum((gross[s] for s in key), ZERO),
                observations=evidence.observations,
                source=evidence.source,
                window_start=evidence.window_start,
                window_end=evidence.window_end,
            )
        )
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
        as_of=state.as_of,
        total_position_market_value=position_value,
        total_portfolio_market_value=total,
        total_cost_basis=basis,
        unrealized_pnl=position_value - basis
        if position_value is not None and basis is not None
        else None,
        cash=cash,
        cash_allocation=cash / total if total is not None and total > 0 else None,
        settled_cash=sum((a.settled_cash for a in state.accounts), ZERO)
        if complete and all(a.settled_cash is not None for a in state.accounts)
        else None,
        unsettled_cash=sum((a.unsettled_cash for a in state.accounts), ZERO)
        if complete and all(a.unsettled_cash is not None for a in state.accounts)
        else None,
        buying_power=sum((a.buying_power for a in state.accounts), ZERO)
        if complete and all(a.buying_power is not None for a in state.accounts)
        else None,
        realized_pnl=state.realized_pnl if complete else None,
        allocation_by_security=tuple(rows),
        top_concentrations=tuple(sorted(rows, key=lambda r: (-gross[r.symbol], r.symbol))[:10]),
        exposure_by_security_type=types,
        sector_exposure=sectors,
        industry_exposure=industries,
        market_cap_exposure=caps,
        magnificent_seven_exposure=sum(
            (v for s, v in gross.items() if s in MAGNIFICENT_SEVEN), ZERO
        )
        if valued
        else None,
        technology_exposure=sum(
            (v for s, v in sectors.items() if s in {"Technology", "Information Technology"}), ZERO
        )
        if valued and "unknown" not in sectors
        else None,
        speculative_exposure=speculative if valued else None,
        crypto_related_exposure=crypto if valued else None,
        swing_exposure=swing if valued else None,
        swing_eligible_exposure=eligible if valued else None,
        thematic_exposure=themes,
        sleeve_exposure=sleeves,
        sleeve_monitoring=monitoring,
        correlated_exposure=tuple(pairs) if pairs else None,
        performance=performance(performance_evidence, as_of=state.as_of),
        experimental_capital=experimental_utilization(state, policy),
        data_gaps=tuple(sorted(set(gaps))),
    )
