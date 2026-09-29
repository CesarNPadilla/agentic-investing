"""Close-only engine: decide at t, execute at t+1 close, mark at that close."""

import hashlib
import itertools
from decimal import Decimal
from statistics import mean, stdev

from simulation.models import SimulationInput, SimulationRun


def evaluate(inputs: SimulationInput, mode="backtest") -> SimulationRun:
    cash = inputs.initial_cash
    quantity = Decimal(0)
    basis = Decimal(0)
    pending = None
    fee = inputs.fee_bps / 10000
    slip = inputs.slippage_bps / 10000
    curve, decisions, fills, trades = [], [], [], []
    closes = []
    benchmark_start = inputs.benchmark.bars[0].close
    peak = cash
    for index, (bar, benchmark) in enumerate(zip(inputs.history.bars, inputs.benchmark.bars)):
        timestamp = bar.timestamp.isoformat()
        if pending is not None:
            side = "buy" if pending else "sell"
            price = bar.close * (1 + slip if pending else 1 - slip)
            if pending and not quantity:
                quantity = cash / (price * (1 + fee))
                cost = quantity * price
                charge = cost * fee
                basis = cash
                cash = Decimal(0)
                fills.append(
                    {
                        "timestamp": timestamp,
                        "side": side,
                        "quantity": str(quantity),
                        "price": str(price),
                        "fee": str(charge),
                        "decision_index": index - 1,
                    }
                )
            elif not pending and quantity:
                proceeds = quantity * price
                charge = proceeds * fee
                cash += proceeds - charge
                trades.append(
                    {
                        "exit_at": timestamp,
                        "pnl": str(proceeds - charge - basis),
                        "return_fraction": str((proceeds - charge) / basis - 1),
                    }
                )
                fills.append(
                    {
                        "timestamp": timestamp,
                        "side": side,
                        "quantity": str(quantity),
                        "price": str(price),
                        "fee": str(charge),
                        "decision_index": index - 1,
                    }
                )
                quantity = Decimal(0)
                basis = Decimal(0)
        equity = cash + quantity * bar.close
        peak = max(peak, equity)
        curve.append(
            {
                "timestamp": timestamp,
                "equity": str(equity),
                "cash": str(cash),
                "quantity": str(quantity),
                "drawdown": str(equity / peak - 1),
                "benchmark_equity": str(inputs.initial_cash * benchmark.close / benchmark_start),
            }
        )
        closes.append(bar.close)
        strategy = inputs.strategy
        fast = slow = None
        if strategy.name == "buy_and_hold":
            target, reason = (
                True,
                "Buy-and-hold targets a long position after the first observation.",
            )
        elif len(closes) < strategy.slow:
            target, reason = False, f"Warm-up: {len(closes)}/{strategy.slow} closes available."
        else:
            fast = sum(closes[-strategy.fast :]) / strategy.fast
            slow = sum(closes[-strategy.slow :]) / strategy.slow
            target = fast > slow
            reason = f"Fast SMA {fast} {'>' if target else '<='} slow SMA {slow}."
        pending = target
        decisions.append(
            {
                "timestamp": timestamp,
                "agent": "deterministic-strategy-v1",
                "strategy_version": strategy.version,
                "target": "long" if target else "cash",
                "action": ("hold" if target == bool(quantity) else "buy" if target else "sell"),
                "reasoning": reason,
                "observed_through": timestamp,
                "bars_seen": index + 1,
                "fast_sma": str(fast) if fast is not None else None,
                "slow_sma": str(slow) if slow is not None else None,
                "execution": "next supplied close",
            }
        )
    equities = [Decimal(point["equity"]) for point in curve]
    returns = [float(b / a - 1) for a, b in itertools.pairwise(equities)]
    volatility = stdev(returns) if len(returns) >= 2 else None
    pnls = [Decimal(trade["pnl"]) for trade in trades]
    wins = sum(pnl > 0 for pnl in pnls)
    losses = sum(pnl < 0 for pnl in pnls)
    gain = sum((pnl for pnl in pnls if pnl > 0), Decimal(0))
    loss = -sum((pnl for pnl in pnls if pnl < 0), Decimal(0))
    total = equities[-1] / inputs.initial_cash - 1
    benchmark_return = inputs.benchmark.bars[-1].close / benchmark_start - 1
    metrics = {
        "total_return": str(total),
        "benchmark_return": str(benchmark_return),
        "excess_return": str(total - benchmark_return),
        "max_drawdown": str(min(Decimal(p["drawdown"]) for p in curve)),
        "volatility_annualized": volatility * 252**0.5 if volatility is not None else None,
        "sharpe_ratio": (mean(returns) / volatility * 252**0.5 if volatility else None),
        "risk_free_rate": 0,
        "annualization_sessions": 252,
        "closed_trades": len(trades),
        "wins": wins,
        "losses": losses,
        "breakeven": len(trades) - wins - losses,
        "win_rate": wins / len(trades) if trades else None,
        "profit_factor": str(gain / loss) if loss else None,
        "realized_pnl": str(sum(pnls, Decimal(0))),
        "unrealized_pnl": str(quantity * closes[-1] - basis),
        "ending_equity": str(equities[-1]),
        "open_position": bool(quantity),
    }
    warnings = [
        "Local simulation only; no broker orders or live execution.",
        "Signals fill at the next supplied close; final signal remains pending.",
        "Fractional long-only shares, full allocation, proportional costs; no liquidity model.",
        "Benchmark is frictionless buy-and-hold from the first close; strategy enters later.",
        "252-session annualization with zero risk-free rate; gaps are not filled.",
        "Selected-symbol history does not control survivorship or strategy-selection bias.",
        "Adjusted prices are synthetic units; dividends/splits are not separate cash events.",
        "Paper sessions accept imported completed bars; no background feed or broker reconciliation.",
    ]
    if inputs.history.is_sample or inputs.benchmark.is_sample:
        warnings.append("Synthetic data: results are illustrative.")
    if inputs.history.adjustment != "all":
        warnings.append(
            "History is not fully adjusted; dividends and/or splits can distort returns."
        )
    digest = hashlib.sha256(inputs.model_dump_json().encode()).hexdigest()
    return SimulationRun(
        mode=mode,
        inputs=inputs,
        dataset_hash=digest,
        metrics=metrics,
        equity_curve=curve,
        decisions=decisions,
        fills=fills,
        closed_trades=trades,
        warnings=warnings,
    )
