"""Deterministic snapshot-to-ledger reconciliation. No broker calls or execution."""

import json
from decimal import Decimal

from portfolio.state import PortfolioState, Reconciliation

ZERO = Decimal(0)


def reconcile(opening: PortfolioState, closing: PortfolioState) -> Reconciliation:
    reasons: list[str] = []

    def issue(code):
        if code not in reasons:
            reasons.append(code)

    if opening.as_of >= closing.as_of:
        issue("invalid_snapshot_interval")
    if (opening.source, opening.environment) != (closing.source, closing.environment):
        issue("source_or_environment_changed")
    if closing.history_start != opening.as_of:
        issue("transaction_window_mismatch")
    for state in (opening, closing):
        if not state.coherent_cutoff:
            issue("non_atomic_broker_reads")
        if state.data_gaps:
            issue("broker_data_gaps")
        if not all(
            (
                state.accounts_complete,
                state.positions_complete,
                state.orders_complete,
                state.transactions_complete,
            )
        ):
            issue("incomplete_snapshot")
        if state.history_start > state.as_of:
            issue("invalid_history_window")
        if not state.accounts:
            issue("missing_accounts")
        accounts = {a.account_id: a for a in state.accounts}
        if len(accounts) != len(state.accounts):
            issue("duplicate_account")
        for rows, key, code in (
            (state.positions, lambda r: (r.account_id, r.symbol), "duplicate_position"),
            (state.open_orders, lambda r: (r.account_id, r.order_id), "duplicate_order"),
            (
                state.transactions,
                lambda r: (r.account_id, r.transaction_id),
                "duplicate_transaction",
            ),
        ):
            if len({key(r) for r in rows}) != len(rows):
                issue(code)
            if any(r.account_id not in accounts for r in rows):
                issue("unknown_account_reference")
        for account in state.accounts:
            if account.currency != "USD":
                issue("unsupported_currency")
            if account.cash is None:
                issue("missing_cash")
            if (
                account.settled_cash is not None
                and account.unsettled_cash is not None
                and account.cash != account.settled_cash + account.unsettled_cash
            ):
                issue("cash_components_mismatch")
        for position in state.positions:
            if position.currency != "USD":
                issue("unsupported_position_currency")
            if (
                position.market_value is not None
                and position.price is not None
                and position.asset_type == "equity"
                and abs(position.market_value - position.quantity * position.price)
                > Decimal("0.01")
            ):
                issue("position_market_value_mismatch")
            if (position.quantity >= 0 and position.marked_value is not None
                    and position.cost_basis is not None and position.broker_unrealized_pnl is not None
                    and abs(position.marked_value-position.cost_basis-position.broker_unrealized_pnl)
                    > Decimal("0.01")):
                issue("broker_unrealized_pnl_mismatch")
        for account in state.accounts:
            holdings = [p for p in state.positions if p.account_id == account.account_id]
            if all(p.marked_value is not None and p.currency == account.currency for p in holdings):
                total = sum((p.marked_value for p in holdings), ZERO)
                if account.broker_market_value is not None and abs(total-account.broker_market_value) > Decimal("0.01"):
                    issue("broker_market_value_mismatch")
                if (account.broker_equity is not None and account.cash is not None
                        and abs(total+account.cash-account.broker_equity) > Decimal("0.01")):
                    issue("broker_equity_mismatch")
        for transaction in state.transactions:
            if not state.history_start < transaction.posted_at <= state.as_of:
                issue("transaction_outside_window")
            account = accounts.get(transaction.account_id)
            if account and transaction.currency != account.currency:
                issue("transaction_currency_mismatch")

    old = {a.account_id: a for a in opening.accounts}
    new = {a.account_id: a for a in closing.accounts}
    if old.keys() != new.keys():
        issue("account_scope_changed")
    old_ids = {(t.account_id, t.transaction_id) for t in opening.transactions}
    if old_ids.intersection((t.account_id, t.transaction_id) for t in closing.transactions):
        issue("replayed_transaction")
    old_orders = {(o.account_id, o.order_id): o for o in opening.open_orders}
    for order in closing.open_orders:
        previous = old_orders.get((order.account_id, order.order_id))
        if previous is not None:
            if order.filled_quantity < previous.filled_quantity:
                issue("order_fill_regression")
            fields = (
                "symbol",
                "side",
                "quantity",
                "limit_price",
                "asset_type",
                "leverage_factor",
                "order_type",
                "time_in_force",
                "session",
                "complex",
            )
            if any(getattr(previous, field) != getattr(order, field) for field in fields):
                issue("order_identity_changed")
    for account_id in old.keys() & new.keys():
        before, after = old[account_id], new[account_id]
        if (before.currency, before.account_type, before.cash_basis) != (
            after.currency,
            after.account_type,
            after.cash_basis,
        ):
            issue("account_metadata_changed")
        events = [t for t in closing.transactions if t.account_id == account_id]
        for field, delta in (
            ("cash", "cash_delta"),
            ("settled_cash", "settled_delta"),
            ("unsettled_cash", "unsettled_delta"),
        ):
            start, end = getattr(before, field), getattr(after, field)
            movements = [getattr(t, delta) for t in events]
            if start is None or end is None or any(v is None for v in movements):
                issue(f"unverified_{field}")
            elif start + sum(movements, ZERO) != end:
                issue(f"{field}_ledger_mismatch")
    expected = {(p.account_id, p.symbol): p.quantity for p in opening.positions}
    for event in closing.transactions:
        if event.quantity_delta is None:
            issue("transaction_quantity_unavailable")
        elif event.symbol is not None:
            key = (event.account_id, event.symbol)
            expected[key] = expected.get(key, ZERO) + event.quantity_delta
    actual = {(p.account_id, p.symbol): p.quantity for p in closing.positions}
    if {k: v for k, v in expected.items() if v} != {k: v for k, v in actual.items() if v}:
        issue("position_ledger_mismatch")

    values, symbols = {}, {}
    priced = all(
        p.marked_value is not None and p.price_as_of is not None and p.price_as_of <= closing.as_of
        for p in closing.positions
    )
    if not priced:
        issue("missing_or_future_position_price")
    currency_ok = all(a.currency == "USD" for a in closing.accounts) and all(
        p.currency == "USD" for p in closing.positions
    )
    if priced and currency_ok:
        for position in closing.positions:
            value = abs(position.marked_value)
            values[json.dumps([position.account_id, position.symbol])] = value
            symbols[position.symbol] = symbols.get(position.symbol, ZERO) + value
    gross = sum(values.values(), ZERO) if priced and currency_ok else None

    def total(field):
        items = [getattr(a, field) for a in closing.accounts]
        return sum(items, ZERO) if currency_ok and all(v is not None for v in items) else None

    cash = total("cash")
    net = sum((p.marked_value for p in closing.positions), ZERO) if priced and currency_ok else None
    equity = cash + net if cash is not None and net is not None else None
    commitment = ZERO
    for order in closing.open_orders:
        if order.status == "unknown":
            issue("unknown_order_status")
        if (
            order.quantity == order.filled_quantity
            or (order.status == "open" and order.filled_quantity != 0)
            or (order.status == "partially_filled" and order.filled_quantity == 0)
        ):
            issue("inconsistent_order_status")
        if order.side == "buy":
            if order.limit_price is None or order.remaining_fees is None:
                issue("unknown_order_commitment")
                commitment = None
            elif commitment is not None:
                commitment += (
                    order.quantity - order.filled_quantity
                ) * order.limit_price + order.remaining_fees
    return Reconciliation(
        passed=not reasons,
        reasons=tuple(reasons),
        gross_exposure=gross,
        per_position=values,
        per_symbol=symbols,
        cash=cash,
        settled_cash=total("settled_cash"),
        unsettled_cash=total("unsettled_cash"),
        buying_power=total("buying_power"),
        equity=equity,
        cash_allocation=cash / equity if equity is not None and equity > 0 else None,
        concentration=max(symbols.values(), default=ZERO) / gross if gross else None,
        open_buy_commitment=commitment if currency_ok else None,
    )
