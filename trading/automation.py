"""Evidence gate for limited automation; this module never submits orders."""

from datetime import datetime
from decimal import Decimal, InvalidOperation


def qualify_strategy(policy, registered_at: datetime, backtest, paper) -> dict:
    reasons = []
    runs = (("backtest", backtest), ("paper", paper))
    for expected_mode, run in runs:
        if run.mode != expected_mode:
            reasons.append(f"Expected {expected_mode} evidence")
        if run.created_at <= registered_at:
            reasons.append(f"{expected_mode.title()} must be created after policy registration")
        strategy = run.inputs.strategy
        if strategy.name != policy.strategy or strategy.version != policy.strategy_version:
            reasons.append(f"{expected_mode.title()} strategy does not match policy")
        if policy.strategy == "sma" and (strategy.fast != policy.fast or strategy.slow != policy.slow):
            reasons.append(f"{expected_mode.title()} SMA windows do not match policy")
        history = run.inputs.history
        benchmark = run.inputs.benchmark
        if history.is_sample or benchmark.is_sample:
            reasons.append(f"{expected_mode.title()} evidence cannot use sample data")
        if history.adjustment != "all" or benchmark.adjustment != "all":
            reasons.append(f"{expected_mode.title()} evidence must be fully adjusted")

    backtest_history = backtest.inputs.history
    paper_history = paper.inputs.history
    if backtest_history.symbol != paper_history.symbol:
        reasons.append("Backtest and paper symbols must match")
    if backtest_history.symbol not in policy.allowed_symbols:
        reasons.append("Evidence symbol is not allowed by policy")
    if not paper_history.bars or paper_history.bars[0].timestamp <= registered_at:
        reasons.append("Paper observations must begin after policy registration")
    if (
        not backtest_history.bars
        or not paper_history.bars
        or paper_history.bars[0].timestamp <= backtest_history.bars[-1].timestamp
    ):
        reasons.append("Paper observations must follow the backtest period")
    if len(paper_history.bars) < 60 or paper.revision < 59:
        reasons.append("Paper evidence requires at least 60 sequential sessions")

    backtest_metrics = backtest.metrics
    paper_metrics = paper.metrics
    _check_minimum(backtest_metrics, "excess_return", Decimal("0.05"), "Backtest", reasons)
    _check_maximum(backtest_metrics, "max_drawdown", Decimal("0.15"), "Backtest", reasons)
    _check_minimum(backtest_metrics, "sharpe_ratio", Decimal("0.8"), "Backtest", reasons)
    _check_minimum(paper_metrics, "total_return", Decimal(0), "Paper", reasons)
    _check_maximum(paper_metrics, "max_drawdown", Decimal("0.10"), "Paper", reasons)
    return {"passed": not reasons, "reasons": reasons}


def _metric(metrics, key):
    try:
        value = metrics[key]
        return Decimal(str(value)) if value is not None else None
    except (KeyError, InvalidOperation, TypeError, ValueError):
        return None


def _check_minimum(metrics, key, minimum, label, reasons):
    value = _metric(metrics, key)
    if value is None or value < minimum:
        reasons.append(f"{label} {key} must be at least {minimum}")


def _check_maximum(metrics, key, maximum, label, reasons):
    value = _metric(metrics, key)
    if value is None or abs(value) > maximum:
        reasons.append(f"{label} {key} must not exceed {maximum}")