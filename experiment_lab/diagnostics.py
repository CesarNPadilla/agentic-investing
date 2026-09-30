"""Observable behavior and explicit unavailable diagnostics; no automatic ranking."""

from collections import Counter
from decimal import Decimal


def summarize(result):
    failures, outcomes, technical = Counter(), Counter(), Counter()
    per_symbol = {}
    for d in result.decisions:
        if "symbol" not in d:
            continue
        symbol = d["symbol"]
        per_symbol.setdefault(symbol, Counter())[d.get("strategy_status", "UNKNOWN")] += 1
        outcomes[d.get("strategy_status", "UNKNOWN")] += 1
        for c in d.get("diagnostics", ()):
            if c["status"] in {"FAIL", "UNSET", "INSUFFICIENT_DATA"}:
                failures[f"{c['name']}:{c['status']}"] += 1
            if c["dimension"] in {"technical", "momentum", "volume", "volatility"}:
                technical[f"{c['name']}:{c['status']}"] += 1
    reviews = [d for d in result.decisions if "risk_status" in d]
    max_positions = max((len(p["positions"]) for p in result.equity_curve), default=0)
    return {
        "securities_filled": sorted({t["symbol"] for t in result.trades}),
        "per_security": {s: dict(sorted(c.items())) for s, c in sorted(per_symbol.items())},
        "failed_gates": dict(sorted(failures.items())),
        "outcomes": dict(sorted(outcomes.items())),
        "technical_conditions": dict(sorted(technical.items())),
        "entries_generated": sum("proposal" in d for d in result.decisions),
        "rejected_entries": sum(
            d["risk_status"] in {"REJECT", "INSUFFICIENT_DATA"} for d in reviews
        ),
        "risk_review_exercised": bool(reviews),
        "risk_findings": dict(
            Counter(reason for d in reviews for reason in d.get("review", {}).get("reasons", ()))
        ),
        "stop_exits": sum("atr_stop_review" in d.get("reasons", ()) for d in result.decisions),
        "trend_exit_reviews": sum(
            any("trend" in reason for reason in d.get("reasons", ()))
            for d in result.decisions
            if d.get("strategy_status") == "EXIT_REVIEW"
        ),
        "false_breakouts": None,
        "false_breakout_limitation": "UNSET outcome definition; no automatic sell policy",
        "high_volatility_behavior": "ATR values and gate outcomes retained; no approved high-volatility classification threshold",
        "maximum_simultaneous_positions": max_positions,
        "total_transaction_fees": str(sum((Decimal(t["fee"]) for t in result.trades), Decimal(0))),
        "average_holding_period": result.metrics.get("average_holding_period"),
    }


def capital_diagnostics(config, dataset, result):
    bars = [
        b
        for b in dataset.bars
        if b.symbol in config.security_universe
        and config.start_date <= b.session_close.date() <= config.end_date
    ]
    prices = {
        s: min(b.close for b in bars if b.symbol == s) for s in sorted({b.symbol for b in bars})
    }
    budget = min(
        config.initial_capital, config.risk_policy.agent_experimental_capital_limit or Decimal(0)
    )
    return {
        "mode": config.capital_mode,
        "starting_cash": str(config.initial_capital),
        "policy_sleeve_limit": str(config.risk_policy.agent_experimental_capital_limit),
        "minimum_observed_whole_share_prices": {s: str(p) for s, p in prices.items()},
        "fractional_required_at_every_observed_price": sorted(
            s for s, p in prices.items() if p > budget
        ),
        "simulator_fractional_enabled": config.execution.fractional_shares,
        "policy_fractional_allowed": config.risk_policy.fractional_orders_allowed,
        "fractional_execution": "BLOCKED_BY_POLICY"
        if config.execution.fractional_shares and not config.risk_policy.fractional_orders_allowed
        else "WHOLE_SHARES_ONLY",
        "minimum_practical_notional": "UNSET: no approved minimum-size or maximum-cost-fraction threshold",
        "diversification": "Cash/whole-share prices and USD 160 sleeve limit constrain simultaneous positions; no forced ownership",
        "cash_utilization": result.metrics.get("cash_utilization"),
        "fee_fraction_of_starting_cash": str(
            sum((Decimal(t["fee"]) for t in result.trades), Decimal(0)) / config.initial_capital
        ),
    }


def sensitivity_summary(rows):
    probes = []
    for row in rows:
        if row["purpose"] != "sensitivity":
            continue
        baseline = next(
            r
            for r in rows
            if r["purpose"] == "baseline"
            and r["strategy_id"] == row["strategy_id"]
            and r["role"] == "development"
            and r["capital_mode"] == row["capital_mode"]
        )
        differences = {
            key: {"baseline": baseline["metrics"].get(key), "probe": row["metrics"].get(key)}
            for key in ("total_return", "maximum_drawdown", "number_of_trades", "cash_utilization")
            if baseline["metrics"].get(key) != row["metrics"].get(key)
        }
        probes.append(
            {
                "strategy_id": row["strategy_id"],
                "version": row["strategy_version"],
                "metric_changes": differences,
                "gate_counts_changed": baseline["diagnostics"]["technical_conditions"]
                != row["diagnostics"]["technical_conditions"],
                "conclusion": "Behavioral probe only; execution fragility is unmeasurable while mandatory controls block fills"
                if not baseline["metrics"].get("number_of_trades")
                and not row["metrics"].get("number_of_trades")
                else "Factual deltas only; no approved materiality threshold and no performance-based selection",
                "selected_for_performance": False,
            }
        )
    return tuple(probes)
