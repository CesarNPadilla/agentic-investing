"""Factual comparisons and fail-closed paper eligibility; no live status exists."""

from decimal import Decimal

from backtesting.models import StrategyValidationReport
from risk.evaluator import digest


def validate(results, gates):
    if not results:
        raise ValueError("At least one backtest required")
    versions = {digest(r.config.strategy) for r in results}
    if len(versions) != 1:
        raise ValueError("Validation requires one exact strategy version")
    checks = {}
    for name in (
        "max_drawdown",
        "minimum_observations",
        "minimum_trades",
        "max_turnover",
        "acceptable_data_quality",
    ):
        threshold = getattr(gates, name)
        if threshold is None:
            checks[name] = "UNSET"
            continue
        passed = True
        for result in results:
            m = result.metrics
            if name == "acceptable_data_quality":
                passed &= set(result.data_quality) <= set(threshold)
            else:
                key = {
                    "max_drawdown": "maximum_drawdown",
                    "minimum_observations": "observations",
                    "minimum_trades": "number_of_trades",
                    "max_turnover": "turnover",
                }[name]
                value = m.get(key)
                passed &= value is not None and (
                    Decimal(str(value)) >= threshold
                    if name.startswith("minimum")
                    else Decimal(str(value)) <= threshold
                )
        checks[name] = "PASS" if passed else "FAIL"
    checks["zero_lookahead_violations"] = (
        "PASS" if all(r.lookahead_violations == 0 for r in results) else "FAIL"
    )
    checks["zero_policy_bypasses"] = (
        "PASS" if all(r.policy_bypasses == 0 for r in results) else "FAIL"
    )
    checks["completed"] = "PASS" if all(r.status == "COMPLETED" for r in results) else "FAIL"
    checks["non_synthetic"] = (
        "FAIL" if any("SYNTHETIC_TEST_DATA" in r.data_quality for r in results) else "PASS"
    )
    checks["holdout"] = (
        "PASS"
        if any(r.config.periods and r.config.evaluated_role == "out_of_sample" for r in results)
        else "UNSET"
    )
    unresolved = sorted(
        {
            w
            for r in results
            for w in r.bias_warnings
            if w
            in {
                "SURVIVORSHIP_BIAS_RISK",
                "IN_SAMPLE_EVALUATION",
                "RETROSPECTIVE_STRATEGY_DEFINITION",
            }
        }
    )
    # Incomplete research/risk reviews cannot qualify a cash-only run via permissive trade gates.
    if any(r.metrics.get("insufficient_data_count", 0) for r in results):
        unresolved.append("INSUFFICIENT_STRATEGY_OR_RISK_EVIDENCE")
    state = (
        "FAIL"
        if "FAIL" in checks.values()
        else "REQUIRES_REVIEW"
        if "UNSET" in checks.values() or unresolved
        else "PASS"
    )
    first = results[0].config.strategy
    return StrategyValidationReport(
        strategy_id=first.strategy_id,
        strategy_version=first.strategy_version,
        backtests_evaluated=tuple(r.config.backtest_id for r in results),
        datasets=tuple(r.dataset_digest for r in results),
        time_periods=tuple(
            {
                "start": str(r.config.start_date),
                "end": str(r.config.end_date),
                "role": r.config.evaluated_role,
            }
            for r in results
        ),
        assumptions=tuple(r.config.model_dump(mode="json") for r in results),
        performance=tuple(r.metrics for r in results),
        data_quality_findings=tuple(sorted({f for r in results for f in r.data_quality})),
        bias_warnings=tuple(sorted({w for r in results for w in r.bias_warnings})),
        gate_results=checks,
        validation_gates=gates,
        unresolved_risks=tuple(unresolved),
        validation_status=state,
        paper_eligibility="ELIGIBLE_FOR_FORWARD_PAPER_VALIDATION"
        if state == "PASS"
        else "REQUIRES_REVIEW"
        if state == "REQUIRES_REVIEW"
        else "NOT_ELIGIBLE",
    )


def compare(results):
    return tuple(
        {
            "backtest_id": r.config.backtest_id,
            "strategy_id": r.config.strategy.strategy_id,
            "strategy_version": r.config.strategy.strategy_version,
            "dataset": r.dataset_digest,
            "start": str(r.config.start_date),
            "end": str(r.config.end_date),
            "assumptions": r.config.execution.model_dump(mode="json"),
            "metrics": r.metrics,
            "status": r.status,
        }
        for r in results
    )
