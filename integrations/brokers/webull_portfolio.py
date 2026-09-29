"""Authenticated Webull SDK reads only. Public field references are in ADR-013.

Cash activities are not a full share/settlement ledger. Never claim they are.
"""

from datetime import UTC, datetime, timedelta
from decimal import Decimal

from pydantic import ValidationError

from integrations.brokers.base import BrokerUnavailable
from integrations.brokers.webull_production import WebullProductionError
from portfolio.state import PortfolioState, StateAccount, StateOrder, StatePosition, Transaction


def number(record, name):
    value = record.get(name)
    if value is None or value == "":
        return None
    if isinstance(value, bool):
        raise TypeError("Invalid number")
    result = Decimal(str(value))
    if not result.is_finite():
        raise ValueError("Invalid number")
    return result


def rows(value):
    if not isinstance(value, list) or not all(isinstance(row, dict) for row in value):
        raise ValueError("Invalid collection")
    return value


def timestamp(value):
    result = datetime.fromisoformat(value)
    if result.tzinfo is None:
        raise ValueError("Timezone missing")
    return result


def iso(value):
    return value.astimezone(UTC).isoformat(timespec="milliseconds").replace("+00:00", "Z")


class WebullPortfolioReader:
    def __init__(self, access, *, clock=lambda: datetime.now(UTC), max_pages=100):
        self.access, self.clock, self.max_pages = access, clock, max_pages

    def _pages(self, fetch):
        result, seen = [], set()
        cursor = None
        for _ in range(self.max_pages):
            payload = fetch(cursor)
            if not isinstance(payload, dict) or "data" not in payload:
                raise ValueError("Invalid page")
            result.extend(rows(payload["data"]))
            cursor = payload.get("pagination_key")
            if cursor is None:
                return result
            if not isinstance(cursor, str) or not cursor or cursor in seen:
                raise ValueError("Invalid/repeated cursor")
            seen.add(cursor)
        raise ValueError("Page limit exceeded")

    @staticmethod
    def _guard(function):
        try:
            return function()
        except (
            WebullProductionError,
            ValidationError,
            ValueError,
            TypeError,
            KeyError,
            AttributeError,
            ArithmeticError,
            OSError,
            TimeoutError,
        ):
            raise BrokerUnavailable("Webull portfolio read unavailable or invalid") from None

    def get_open_orders(self, account_id):
        def read():
            groups = self._pages(lambda key: self.access.get_open_orders_page(account_id, key))
            result, seen = [], set()
            for group in groups:
                for item in rows(group["orders"]):
                    order_id = item["order_id"]
                    if order_id in seen:
                        raise ValueError("Duplicate order")
                    seen.add(order_id)
                    result.append(
                        StateOrder(
                            account_id=account_id,
                            order_id=order_id,
                            symbol=item["symbol"],
                            side=item["side"].lower(),
                            quantity=item["total_quantity"],
                            filled_quantity=item["filled_quantity"],
                            limit_price=number(item, "limit_price"),
                            # Remaining fees are not supplied by this endpoint.
                            remaining_fees=None,
                            status={
                                "PENDING": "open",
                                "SUBMITTED": "open",
                                "PARTIAL_FILLED": "partially_filled",
                            }.get(item["status"], "unknown"),
                            asset_type={"EQUITY": "equity", "OPTION": "option"}.get(
                                item.get("instrument_type"), "unknown"
                            ),
                            order_type=item.get("order_type", "unknown").lower(),
                            time_in_force=item.get("time_in_force", "unknown").lower(),
                            session=item.get("support_trading_session", "unknown").lower(),
                            complex=(
                                group.get("combo_type") != "NORMAL"
                                or item.get("option_strategy", "SINGLE") != "SINGLE"
                                or bool(item.get("algo_type"))
                                or bool(item.get("legs"))
                            ),
                        )
                    )
            return result

        return self._guard(read)

    def get_transactions(self, account_id, start, end):
        def read():
            if start.tzinfo is None or end.tzinfo is None or start >= end:
                raise ValueError("Invalid history window")
            start_utc, end_utc = start.astimezone(UTC), end.astimezone(UTC)
            if end_utc.year - start_utc.year > 10:
                raise ValueError("History window too large")
            result, seen = [], set()
            window = start_utc
            while window <= end_utc:
                next_year = datetime(window.year + 1, 1, 1, tzinfo=UTC)
                stop = min(end_utc, next_year - timedelta(milliseconds=1))
                data = self._pages(
                    lambda key, a=window, b=stop: self.access.get_transactions_page(
                        account_id, iso(a), iso(b), key
                    )
                )
                for item in data:
                    if item["account_id"] != account_id or item["id"] in seen:
                        raise ValueError("Duplicate/cross-account activity")
                    seen.add(item["id"])
                    posted = timestamp(item["biz_time"])
                    if posted == start:
                        continue
                    if not start < posted <= end:
                        raise ValueError("Activity outside requested window")
                    cash_only = item["activity_type"] in {
                        "DEPOSIT",
                        "WITHDRAW",
                        "FEES",
                        "DIVIDENDS",
                        "TAX",
                        "INTERESTS",
                    }
                    result.append(
                        Transaction(
                            account_id=account_id,
                            transaction_id=item["id"],
                            posted_at=posted,
                            currency=item["currency"],
                            kind="broker_activity",
                            symbol=item.get("symbol") or None,
                            cash_delta=item["net_amount"],
                            quantity_delta=Decimal(0) if cash_only else None,
                            settled_delta=None,
                            unsettled_delta=None,
                            activity_type=item["activity_type"],
                            activity_sub_type=item.get("activity_sub_type"),
                        )
                    )
                window = next_year
            return result

        return self._guard(read)

    def read_state(self, *, history_start):
        def read():
            started = self.clock()
            if history_start.tzinfo is None or history_start >= started:
                raise ValueError("History start must precede read")
            account_rows = rows(self.access.list_accounts())
            ids = [item["account_id"] for item in account_rows]
            if len(set(ids)) != len(ids):
                raise ValueError("Duplicate account")
            accounts, positions, orders, transactions = [], [], [], []
            gaps = [
                "non_atomic_broker_reads",
                "transaction_coverage_cash_activities_only",
                "position_price_timestamp_unavailable",
                "cash_reservation_semantics_unverified",
            ]
            orders_complete = True
            for raw_account in account_rows:
                account_id = raw_account["account_id"]
                balance = self.access.get_balance(account_id)
                currency = balance["total_asset_currency"]
                assets = rows(balance["account_currency_assets"])
                if len(assets) != 1 or assets[0]["currency"] != currency:
                    raise ValueError("Multi-currency accounts need explicit FX support")
                asset = assets[0]
                accounts.append(
                    StateAccount(
                        account_id=account_id,
                        currency=currency,
                        account_type={"CASH": "cash", "MARGIN": "margin"}.get(
                            raw_account.get("account_type"), "unknown"
                        ),
                        cash=number(asset, "cash_balance"),
                        settled_cash=number(asset, "settled_cash"),
                        unsettled_cash=number(asset, "unsettled_cash"),
                        buying_power=number(asset, "buying_power"),
                        broker_market_value=number(asset, "market_value"),
                        broker_equity=number(asset, "net_liquidation_value"),
                    )
                )
                seen = set()
                for item in rows(self.access.get_positions(account_id)):
                    if item["symbol"] in seen:
                        raise ValueError("Duplicate position requires explicit lot aggregation")
                    seen.add(item["symbol"])
                    quantity, price, cost = (
                        number(item, key) for key in ("quantity", "last_price", "cost_price")
                    )
                    equity = item.get("instrument_type") == "EQUITY"
                    positions.append(
                        StatePosition(
                            account_id=account_id,
                            symbol=item["symbol"],
                            quantity=quantity,
                            currency=item["currency"],
                            price=price if price and price > 0 else None,
                            cost_basis=abs(quantity) * cost
                            if equity and cost is not None
                            else None,
                            market_value=quantity * price if equity and price is not None else None,
                            broker_unrealized_pnl=number(item, "unrealized_profit_loss"),
                            asset_type="equity"
                            if equity
                            else (
                                "option" if item.get("instrument_type") == "OPTION" else "unknown"
                            ),
                            observed_at=self.clock(),
                        )
                    )
                try:
                    orders.extend(self.get_open_orders(account_id))
                except BrokerUnavailable:
                    orders_complete = False
                    gaps.append("open_orders_unavailable")
            cutoff = self.clock()
            for account_id in ids:
                try:
                    transactions.extend(self.get_transactions(account_id, history_start, cutoff))
                except BrokerUnavailable:
                    gaps.append("transactions_unavailable")
            return PortfolioState(
                source="webull-production-read-only",
                environment="production",
                as_of=cutoff,
                read_started_at=started,
                history_start=history_start,
                accounts_complete=True,
                positions_complete=True,
                orders_complete=orders_complete,
                # Cash activities omit share deltas and settlement transfers/in-kind events.
                transactions_complete=False,
                coherent_cutoff=False,
                accounts=tuple(accounts),
                positions=tuple(positions),
                open_orders=tuple(orders),
                transactions=tuple(transactions),
                data_gaps=tuple(sorted(set(gaps))),
            )

        return self._guard(read)
