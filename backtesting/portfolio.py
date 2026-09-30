"""Deterministic long-only ledger. Internal fills are never broker orders."""

from datetime import timedelta
from decimal import Decimal
from zoneinfo import ZoneInfo

from portfolio.state import (
    ExperimentalAttribution,
    ExperimentalPosition,
    PortfolioState,
    StateAccount,
    StatePosition,
    Transaction,
)

ZERO = Decimal(0)


class PortfolioSimulator:
    def __init__(self, config):
        self.config = config
        self.cash = config.initial_capital
        self.positions = {}
        self.realized = ZERO
        self.income = ZERO
        self.transactions = []
        self.trades = []
        self.day = None
        self.day_equity = config.initial_capital

    def equity(self, marks):
        return self.cash + sum((p["quantity"] * marks[s] for s, p in self.positions.items()), ZERO)

    def begin_day(self, now, marks):
        zone = self.config.risk_policy.daily_loss_timezone
        day = now.astimezone(ZoneInfo(zone)).date() if zone else now.date()
        if day != self.day:
            self.day_equity = self.equity(marks)
            self.day = day

    def movement(self, now, symbol, quantity, cash, kind):
        self.transactions.append(
            Transaction(
                account_id=self.config.account_id,
                transaction_id=f"ledger-{len(self.transactions)}",
                posted_at=now,
                currency="USD",
                kind=kind,
                symbol=symbol,
                quantity_delta=quantity,
                cash_delta=cash,
                settled_delta=cash,
                unsettled_delta=ZERO,
            )
        )

    def action(self, action):
        position = self.positions.get(action.symbol)
        if position is None:
            return
        if action.kind == "split":
            old = position["quantity"]
            position["quantity"] *= action.ratio
            position["peak_price"] /= action.ratio
            self.movement(
                action.effective_at, action.symbol, position["quantity"] - old, ZERO, "adjustment"
            )
        elif action.kind == "dividend":
            amount = position["quantity"] * action.cash_per_share
            self.cash += amount
            self.income += amount
            # Adjust the per-share peak for the cash distribution, like an ex-dividend series.
            position["peak_price"] = max(
                Decimal("0.00000001"), position["peak_price"] - action.cash_per_share
            )
            self.movement(action.effective_at, action.symbol, ZERO, amount, "adjustment")

    def quote(self, side, quantity, close):
        assumptions = self.config.execution
        impact = (assumptions.slippage_bps + assumptions.spread_bps / 2) / 10000
        price = close * (1 + impact if side == "buy" else 1 - impact)
        fee = assumptions.commission_fixed + quantity * price * assumptions.commission_bps / 10000
        return price, fee

    def fill(self, proposal, now, price, fee, marks, risk_decision):
        """Accounting primitive; engine alone supplies independently reviewed proposals."""
        trade = proposal.trade
        quantity, symbol, side = trade.quantity, trade.symbol, trade.side
        position = self.positions.get(symbol)
        if not self.config.execution.fractional_shares and quantity != quantity.to_integral_value():
            return "FRACTIONAL_SHARES_DISABLED"
        cost = quantity * price
        if side == "buy":
            if cost + fee > self.cash:
                return "INSUFFICIENT_CASH"
            equity = self.equity(marks) - fee
            exposure = (
                sum((p["quantity"] * marks[s] for s, p in self.positions.items()), ZERO) + cost
            )
            if equity <= 0 or exposure > equity * self.config.execution.max_exposure:
                return "MAX_EXPOSURE"
            symbol_value = (position["quantity"] * marks[symbol] if position else ZERO) + cost
            ceiling = self.config.execution.max_position_value
            if ceiling is not None and symbol_value > ceiling:
                return "POSITION_LIMIT"
            if position is None:
                position = {
                    "quantity": ZERO,
                    "basis": ZERO,
                    "entered_at": now,
                    "peak_price": price,
                    "max_drawdown": ZERO,
                }
                self.positions[symbol] = position
            position["quantity"] += quantity
            position["basis"] += cost + fee
            self.cash -= cost + fee
            pnl, holding = None, None
            self.movement(now, symbol, quantity, -cost - fee, "fill")
        else:
            if position is None or quantity > position["quantity"]:
                return "LONG_ONLY"
            if self.cash + cost - fee < 0:
                return "INSUFFICIENT_CASH"
            basis = position["basis"] * quantity / position["quantity"]
            pnl = cost - fee - basis
            holding = Decimal(str((now - position["entered_at"]).total_seconds() / 86400))
            self.realized += pnl
            self.cash += cost - fee
            position["quantity"] -= quantity
            position["basis"] -= basis
            if not position["quantity"]:
                del self.positions[symbol]
            self.movement(now, symbol, -quantity, cost - fee, "fill")
        self.trades.append(
            {
                "trade_id": f"{self.config.backtest_id}-fill-{len(self.trades)}",
                "proposal_id": proposal.proposal_id,
                "strategy_id": proposal.strategy_id,
                "strategy_version": proposal.strategy_version,
                "opportunity_id": proposal.opportunity_id,
                "symbol": symbol,
                "side": side,
                "signal_timestamp": proposal.timestamp.isoformat(),
                "execution_timestamp": now.isoformat(),
                "execution_price": str(price),
                "quantity": str(quantity),
                "notional": str(cost),
                "fee": str(fee),
                "entry_rationale": proposal.proposed_entry,
                "exit_rationale": proposal.proposed_exit_logic,
                "realized_result": str(pnl) if pnl is not None else None,
                "holding_days": str(holding) if holding is not None else None,
                "assumptions": self.config.execution.model_dump(mode="json"),
                "risk_decision": risk_decision,
            }
        )
        return "FILLED"

    def state(self, now, marks, opening_time):
        config = self.config
        equity = self.equity(marks)
        positions = tuple(
            StatePosition(
                account_id=config.account_id,
                symbol=s,
                quantity=p["quantity"],
                price=marks[s],
                cost_basis=p["basis"],
                price_as_of=now,
                asset_type="equity",
                leverage_factor=1,
            )
            for s, p in sorted(self.positions.items())
        )
        zone = config.risk_policy.daily_loss_timezone
        day_start = (
            now.astimezone(ZoneInfo(zone)).replace(hour=0, minute=0, second=0, microsecond=0)
            if zone
            else None
        )
        return PortfolioState(
            source="offline-backtest",
            environment="research",
            as_of=now,
            history_start=opening_time,
            accounts_complete=True,
            positions_complete=True,
            orders_complete=True,
            transactions_complete=True,
            accounts=(
                StateAccount(
                    account_id=config.account_id,
                    currency="USD",
                    account_type="cash",
                    cash=self.cash,
                    settled_cash=self.cash,
                    unsettled_cash=ZERO,
                    buying_power=self.cash,
                    cash_basis="before_reservations",
                ),
            ),
            positions=positions,
            open_orders=(),
            transactions=tuple(t for t in self.transactions if opening_time < t.posted_at <= now),
            experimental_attribution=ExperimentalAttribution(
                baseline_id=config.backtest_id,
                source="explicit-simulation-config",
                as_of=now,
                complete=True,
                account_ids=(config.account_id,),
                open_orders=(),
                realized_pnl=self.realized + self.income,
                positions=tuple(
                    ExperimentalPosition(
                        account_id=config.account_id,
                        symbol=p.symbol,
                        quantity=p.quantity,
                        cost_basis=p.cost_basis,
                        strategy_id=config.strategy.strategy_id,
                        strategy_domain=config.strategy.strategy_domain,
                    )
                    for p in positions
                ),
            ),
            daily_pnl=equity - self.day_equity,
            experimental_pnl=equity - config.initial_capital,
            experimental_strategy_pnl={
                config.strategy.strategy_id: equity - config.initial_capital
            },
            realized_pnl=self.realized + self.income,
            daily_pnl_start=day_start,
            daily_pnl_as_of=now,
        )

    def record(self, now, marks, benchmark_equity, peak):
        equity = self.equity(marks)
        holdings = {}
        for symbol, position in sorted(self.positions.items()):
            price = marks[symbol]
            position["peak_price"] = max(position["peak_price"], price)
            position["max_drawdown"] = min(
                position["max_drawdown"], price / position["peak_price"] - 1
            )
            value = position["quantity"] * price
            holdings[symbol] = {
                "quantity": str(position["quantity"]),
                "average_cost": str(position["basis"] / position["quantity"]),
                "cost_basis": str(position["basis"]),
                "market_value": str(value),
                "unrealized_pnl": str(value - position["basis"]),
                "allocation": str(value / equity) if equity else "0",
                "max_drawdown": str(-position["max_drawdown"]),
                "entered_at": position["entered_at"].isoformat(),
                "holding_days": (now - position["entered_at"]).total_seconds() / 86400,
            }
        return {
            "timestamp": now.isoformat(),
            "equity": str(equity),
            "cash": str(self.cash),
            "exposure": str((equity - self.cash) / equity) if equity else "0",
            "positions": holdings,
            "realized_pnl": str(self.realized),
            "dividend_income": str(self.income),
            "unrealized_pnl": str(
                sum((Decimal(p["unrealized_pnl"]) for p in holdings.values()), ZERO)
            ),
            "drawdown": str(1 - equity / max(peak, equity)),
            "benchmark_equity": str(benchmark_equity),
        }

    def initial_state(self, now):
        return self.state(now - timedelta(microseconds=1), {}, now - timedelta(microseconds=2))
