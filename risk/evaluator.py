"""Pure hypothetical checks plus redacted structured logging; no execution dependency."""

import hashlib
import json
import logging
from datetime import datetime
from decimal import Decimal
from typing import Literal
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from pydantic import AwareDatetime, Field

from market_data.models import Symbol
from portfolio.intelligence import experimental_utilization
from portfolio.reconciliation import reconcile
from portfolio.state import Nonnegative, PortfolioState, Record
from risk.policy import InvestmentPolicy

logger = logging.getLogger("investment_policy.audit")
ZERO = Decimal(0)


def digest(value) -> str:
    def canonical(item):
        if hasattr(item, "model_dump"):
            return canonical(item.model_dump(mode="python"))
        if isinstance(item, dict):
            return {k: canonical(v) for k, v in item.items()}
        if isinstance(item, (set, frozenset)):
            return sorted(canonical(v) for v in item)
        if isinstance(item, (tuple, list)):
            return [canonical(v) for v in item]
        if isinstance(item, (Decimal, datetime)):
            return str(item)
        return item

    encoded = json.dumps(canonical(value), sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(encoded.encode()).hexdigest()


class HypotheticalTrade(Record):
    account_id: str = Field(min_length=1)
    symbol: Symbol
    side: Literal["buy", "sell"]
    quantity: Decimal = Field(gt=0, allow_inf_nan=False)
    limit_price: Decimal = Field(gt=0, allow_inf_nan=False)
    estimated_fees: Nonnegative | None = None
    currency: str = "USD"
    asset_type: Literal["equity", "option", "unknown"] = "unknown"
    leverage_factor: Nonnegative | None = None
    order_type: str = "limit"
    time_in_force: str = "day"
    session: str = "core"
    complex: bool = False
    thesis: str | None = None
    entry_thesis: str | None = None
    exit_invalidation_thesis: str | None = None


class KillSwitch(Record):
    enabled: bool | None = None
    as_of: AwareDatetime | None = None


class Check(Record):
    code: str
    passed: bool
    explanation: str


class RiskEvaluation(Record):
    version: Literal["investment-risk-v3"] = "investment-risk-v3"
    evaluated_at: AwareDatetime
    input_digest: str
    policy_digest: str
    allowed: bool
    execution_available: Literal[False] = False
    checks: tuple[Check, ...]
    warnings: tuple[str, ...] = ()
    projected_exposure: Decimal | None
    projected_capital: Decimal | None
    projected_concentration: Decimal | None


def evaluate(
    policy: InvestmentPolicy,
    opening: PortfolioState,
    state: PortfolioState,
    trade: HypotheticalTrade,
    kill_switch: KillSwitch,
    *,
    now: datetime,
) -> RiskEvaluation:
    if now.tzinfo is None or now.utcoffset() is None:
        raise ValueError("Evaluation time must be timezone-aware")
    checks = []

    def check(code, passed, explanation):
        checks.append(Check(code=code, passed=bool(passed), explanation=explanation))

    report = reconcile(opening, state)
    for field in ("thesis", "entry_thesis", "exit_invalidation_thesis"):
        value = getattr(trade, field)
        check(
            field,
            value is not None and bool(value.strip()),
            f"An explicit nonblank {field} is required; presence does not validate its quality",
        )
    check(
        "experimental_loss_control",
        policy.max_experimental_loss is not None
        and state.experimental_pnl is not None
        and -state.experimental_pnl < policy.max_experimental_loss,
        "Experimental loss limit and flow-adjusted experiment-to-date P&L are required",
    )
    check(
        "reconciled",
        report.passed,
        "Complete ledger reconciliation required: " + (", ".join(report.reasons) or "matched"),
    )
    check(
        "environment",
        state.environment in {policy.environment, "production"},
        "Production data may inform research; production execution remains unavailable",
    )
    for field in (
        "max_daily_loss",
        "agent_experimental_capital_limit",
        "max_state_age_seconds",
        "daily_loss_timezone",
    ):
        check(
            f"configured_{field}",
            getattr(policy, field) is not None,
            f"Required control {field} must be explicitly configured",
        )
    age = policy.max_state_age_seconds

    def fresh(timestamp):
        return (
            age is not None
            and timestamp is not None
            and 0 <= (now - timestamp).total_seconds() <= age
        )

    check("fresh_state", fresh(state.as_of), "State must be neither stale nor future-dated")
    check(
        "fresh_prices",
        all(fresh(p.price_as_of) for p in state.positions),
        "Every position requires a fresh mark",
    )
    check(
        "kill_switch",
        kill_switch.enabled is False and fresh(kill_switch.as_of),
        "Kill switch must be present, fresh, and explicitly disengaged",
    )
    check(
        "cash_accounts",
        all(a.account_type == "cash" for a in state.accounts),
        "Margin or unknown account types are forbidden",
    )
    check(
        "cash_semantics",
        all(a.cash_basis == "before_reservations" for a in state.accounts),
        "Cash must be gross ledger cash; reservation semantics cannot be unknown",
    )
    check(
        "cash_components",
        all(
            a.settled_cash is not None
            and a.settled_cash >= 0
            and a.unsettled_cash is not None
            and a.unsettled_cash >= 0
            for a in state.accounts
        ),
        "Known nonnegative settlement balances are required; no borrowing",
    )

    def permitted_instrument(item):
        return (
            item.symbol in policy.new_purchase_allowlist
            and item.symbol in {"AAPL", "MSFT", "SPY"}
            and item.asset_type == "equity"
            and item.leverage_factor == 1
            and item.quantity >= 0
            and item.quantity == item.quantity.to_integral_value()
        )

    def permitted_order(item):
        return (
            permitted_instrument(item)
            and item.side == "buy"
            and not item.complex
            and (item.order_type, item.time_in_force, item.session) == ("limit", "day", "core")
            and (
                not hasattr(item, "filled_quantity")
                or item.filled_quantity == item.filled_quantity.to_integral_value()
            )
        )

    check(
        "proposed_order",
        permitted_order(trade) and trade.currency == policy.currency,
        "Only allowed unlevered equities, whole-share BUY LIMIT/DAY/CORE orders are permitted",
    )
    check(
        "existing_positions",
        all(
            p.asset_type == "equity" and p.leverage_factor == 1 and p.quantity >= 0
            for p in state.positions
        ),
        "Existing holdings are analyzed regardless of purchase allowlist; never auto-liquidated",
    )
    check(
        "existing_orders",
        all(
            permitted_order(o) and o.limit_price is not None and o.limit_price > 0
            for o in state.open_orders
            if state.experimental_attribution is not None
            and any(
                a.account_id == o.account_id and a.order_id == o.order_id
                for a in state.experimental_attribution.open_orders
            )
        ),
        "Only attributed experimental orders must satisfy the agent purchase policy",
    )
    check(
        "known_fees",
        trade.estimated_fees is not None,
        "A fee estimate is required; unknown fees cannot be treated as zero",
    )
    notional = trade.quantity * trade.limit_price
    cost = notional + trade.estimated_fees if trade.estimated_fees is not None else None
    pending = report.open_buy_commitment
    projected = (
        report.gross_exposure + pending + notional
        if report.gross_exposure is not None and pending is not None
        else None
    )
    sleeve = experimental_utilization(state, policy)
    capital = sleeve.utilized + cost if sleeve.valid and cost is not None else None
    check(
        "experimental_attribution",
        sleeve.valid and trade.account_id in state.experimental_attribution.account_ids,
        "Reviewed experimental inventory required: " + (", ".join(sleeve.reasons) or "verified"),
    )
    limit = policy.agent_experimental_capital_limit
    check(
        "experimental_capital",
        capital is not None and limit is not None and capital <= limit,
        f"Attributed acquisition cost plus attributed open buys and proposal: {capital}; cap: {limit}",
    )
    account = next((a for a in state.accounts if a.account_id == trade.account_id), None)
    account_pending = ZERO
    for order in state.open_orders:
        if order.account_id == trade.account_id and order.side == "buy":
            if order.limit_price is None or order.remaining_fees is None:
                account_pending = None
                break
            account_pending += (
                order.quantity - order.filled_quantity
            ) * order.limit_price + order.remaining_fees
    check(
        "settled_cash",
        account is not None
        and account.settled_cash is not None
        and account_pending is not None
        and cost is not None
        and cost + account_pending <= account.settled_cash,
        "Only target-account settled cash funds the proposal and all outstanding buys",
    )
    check(
        "buying_power",
        account is not None
        and account.buying_power is not None
        and cost is not None
        and cost <= account.buying_power,
        "Broker-reported buying power is an additional ceiling, never a cash substitute",
    )
    check(
        "no_leverage",
        projected is not None
        and trade.estimated_fees is not None
        and report.equity is not None
        and projected + trade.estimated_fees <= report.equity,
        "Projected marked commitments and fees must not exceed portfolio equity",
    )
    projected_symbols = dict(report.per_symbol)
    known = report.gross_exposure is not None
    for order in state.open_orders:
        if order.side == "buy":
            if order.limit_price is None:
                known = False
            else:
                projected_symbols[order.symbol] = (
                    projected_symbols.get(order.symbol, ZERO)
                    + (order.quantity - order.filled_quantity) * order.limit_price
                )
    projected_symbols[trade.symbol] = projected_symbols.get(trade.symbol, ZERO) + notional
    gross = sum(projected_symbols.values(), ZERO)
    concentration = max(projected_symbols.values()) / gross if known and gross else None
    check(
        "position_limit",
        policy.max_position_exposure is None
        or (known and max(projected_symbols.values()) <= policy.max_position_exposure),
        "Optional symbol exposure cap; null means no additional cap beyond total exposure",
    )
    check(
        "concentration_limit",
        policy.max_concentration is None
        or (concentration is not None and concentration <= policy.max_concentration),
        "Optional largest-symbol/gross-exposure cap; null means reporting only",
    )
    day_valid = False
    if policy.daily_loss_timezone:
        try:
            zone = ZoneInfo(policy.daily_loss_timezone)
            start = now.astimezone(zone).replace(hour=0, minute=0, second=0, microsecond=0)
            day_valid = state.daily_pnl_start == start and state.daily_pnl_as_of == state.as_of
        except (ZoneInfoNotFoundError, ValueError):
            pass
    check(
        "daily_loss",
        day_valid
        and state.daily_pnl is not None
        and policy.max_daily_loss is not None
        and -state.daily_pnl < policy.max_daily_loss,
        "Flow-adjusted realized plus unrealized daily P&L must be known and loss below the stop",
    )
    warnings = []
    if report.equity is not None and report.equity > 0 and report.gross_exposure is not None:
        for symbol, value in sorted(report.per_symbol.items()):
            weight = value / report.equity
            if weight > policy.severe_concentration_warning:
                warnings.append(f"severe_concentration:{symbol}")
            elif weight > policy.concentration_warning:
                warnings.append(f"concentration:{symbol}")
    else:
        warnings.append("concentration_unavailable")
    result = RiskEvaluation(
        evaluated_at=now,
        input_digest=digest((policy, opening, state, trade, kill_switch, now)),
        policy_digest=digest(policy),
        allowed=all(c.passed for c in checks),
        checks=tuple(checks),
        warnings=tuple(warnings),
        projected_exposure=projected,
        projected_capital=capital,
        projected_concentration=concentration,
    )
    # No raw account IDs, balances, credentials or payloads in application logs.
    logger.info(
        json.dumps(
            {
                "event": "hypothetical_trade_evaluated",
                "version": result.version,
                "input_digest": result.input_digest,
                "policy_digest": result.policy_digest,
                "allowed": result.allowed,
                "execution_available": False,
                "checks": [{"code": c.code, "passed": c.passed} for c in checks],
                "warning_count": len(result.warnings),
            }
        )
    )
    return result
