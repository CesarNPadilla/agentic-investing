"""Metrics use positive drawdown magnitudes and explicit annualization assumptions."""

import itertools
from decimal import Decimal
from math import sqrt
from statistics import mean, stdev


def metrics(config, curve, trades, decisions):
    if not curve:
        return {}
    initial = config.initial_capital
    equities = [Decimal(p["equity"]) for p in curve]
    returns = [float(b / a - 1) for a, b in itertools.pairwise(equities) if a > 0]
    pnl = [Decimal(t["realized_result"]) for t in trades if t["realized_result"] is not None]
    wins, losses = [p for p in pnl if p > 0], [p for p in pnl if p < 0]
    volatility = stdev(returns) if len(returns) > 1 else None
    downside = sqrt(mean(min(r, 0) ** 2 for r in returns)) if returns else None
    rf = config.annual_risk_free_rate
    excess = (
        [r - ((1 + float(rf)) ** (1 / config.annual_sessions) - 1) for r in returns]
        if rf is not None
        else []
    )
    downside_excess = sqrt(mean(min(r, 0) ** 2 for r in excess)) if excess else None
    total = equities[-1] / initial - 1
    benchmark = Decimal(curve[-1]["benchmark_equity"]) / initial - 1
    benchmark_equities = [Decimal(p["benchmark_equity"]) for p in curve]
    benchmark_peak = benchmark_equities[0]
    benchmark_drawdown = Decimal(0)
    for equity in benchmark_equities:
        benchmark_peak = max(benchmark_peak, equity)
        benchmark_drawdown = max(benchmark_drawdown, 1 - equity / benchmark_peak)
    days = (config.end_date - config.start_date).days
    streak = longest = 0
    for value in pnl:
        streak = streak + 1 if value < 0 else 0
        longest = max(longest, streak)
    exposures = [Decimal(p["exposure"]) for p in curve]
    statuses = [d.get("risk_status") for d in decisions]
    return {
        "starting_capital": str(initial),
        "ending_capital": str(equities[-1]),
        "total_return": str(total),
        "annualized_return": (float(equities[-1] / initial) ** (365.25 / days) - 1)
        if days >= 365
        else None,
        "benchmark_return": str(benchmark),
        "benchmark_maximum_drawdown": str(benchmark_drawdown),
        "benchmark_basis": config.benchmark_basis,
        "strategy_return_basis": "total_return_cash_dividends_not_reinvested",
        "excess_return": str(total - benchmark),
        "realized_pnl": curve[-1]["realized_pnl"],
        "unrealized_pnl": curve[-1]["unrealized_pnl"],
        "dividend_income": curve[-1]["dividend_income"],
        "number_of_trades": len(trades),
        "closed_trades": len(pnl),
        "winning_trades": len(wins),
        "losing_trades": len(losses),
        "win_rate": len(wins) / len(pnl) if pnl else None,
        "average_gain": str(sum(wins) / len(wins)) if wins else None,
        "average_loss": str(sum(losses) / len(losses)) if losses else None,
        "profit_factor": str(-sum(wins) / sum(losses)) if losses else None,
        "maximum_drawdown": str(max(Decimal(p["drawdown"]) for p in curve)),
        "average_drawdown": str(sum(Decimal(p["drawdown"]) for p in curve) / len(curve)),
        "volatility": volatility * sqrt(config.annual_sessions) if volatility is not None else None,
        "downside_volatility": downside * sqrt(config.annual_sessions)
        if downside is not None
        else None,
        "sharpe_ratio": mean(excess) / volatility * sqrt(config.annual_sessions)
        if excess and volatility
        else None,
        "sortino_ratio": mean(excess) / downside_excess * sqrt(config.annual_sessions)
        if downside_excess
        else None,
        "turnover": str(
            sum((Decimal(t["notional"]) for t in trades), Decimal(0))
            / (sum(equities) / len(equities))
        ),
        "average_holding_period": mean(
            float(t["holding_days"]) for t in trades if t["holding_days"] is not None
        )
        if pnl
        else None,
        "maximum_exposure": str(max(exposures)),
        "cash_utilization": str(sum(exposures) / len(exposures)),
        "largest_loss": str(min(losses)) if losses else None,
        "consecutive_losses": longest,
        "maximum_position_drawdown": str(
            max(
                (Decimal(h["max_drawdown"]) for p in curve for h in p["positions"].values()),
                default=Decimal(0),
            )
        ),
        "maximum_concentration": str(
            max(
                (Decimal(h["allocation"]) for p in curve for h in p["positions"].values()),
                default=Decimal(0),
            )
        ),
        "risk_engine_rejection_count": statuses.count("REJECT"),
        "insufficient_data_count": statuses.count("INSUFFICIENT_DATA")
        + sum(d.get("strategy_status") == "INSUFFICIENT_DATA" for d in decisions),
        "human_review_count": statuses.count("REQUIRE_HUMAN_REVIEW"),
        "observations": len(curve),
    }
