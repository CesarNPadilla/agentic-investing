"""Additional lab gates retain existing validation and require human review."""

from backtesting.validation import validate


def required_controls(version, policy):
    missing = [
        f"risk_policy.{name}"
        for name in (
            "max_daily_loss",
            "max_experimental_loss",
            "max_state_age_seconds",
            "daily_loss_timezone",
            "agent_experimental_capital_limit",
        )
        if getattr(policy, name) is None
    ]
    c, p = version.configuration, version.experiment
    missing += [
        f"entry.{name}"
        for name in ("fixed_notional", "concentration_ceiling")
        if getattr(c, name) is None
        and (name != "fixed_notional" or version.strategy_domain == "long_term")
    ]
    missing += [
        f"entry.{name}"
        for name in ("valuation_decision", "portfolio_fit_decision")
        if getattr(c, name) == "UNSET"
    ]
    if not version.authorization_reference:
        missing.append("strategy.authorization_reference")
    missing += [f"fundamental.{r.name}" for r in p.metric_rules if r.threshold is None]
    if version.strategy_domain == "swing":
        missing += [
            f"swing.{name}"
            for name in (
                "atr_stop_multiple",
                "max_holding_sessions",
                "max_holding_days",
                "parameters_approved_reference",
            )
            if getattr(p, name) is None
        ]
        missing += [
            f"sizing.{name}"
            for name in ("risk_budget", "max_notional")
            if getattr(version.swing, name) is None
        ]
        missing += [
            f"swing_policy.{name}"
            for name in ("max_position_capital", "max_loss", "max_holding_days", "stop_rule")
            if getattr(policy.swing_controls, name) is None
        ]
    return tuple(sorted(missing))


def lab_validation(results, gates, *, reproducible, fresh_oos):
    report = validate(results, gates)
    missing = sorted(
        {
            name
            for r in results
            for name in required_controls(r.config.strategy, r.config.risk_policy)
        }
    )
    checks = report.gate_results | {
        "reproducible_results": "PASS" if reproducible else "FAIL",
        "preregistered_unexposed_oos": "PASS" if fresh_oos else "FAIL",
        "required_risk_and_strategy_parameters": "UNSET" if missing else "PASS",
        "human_review_required": "PASS",
    }
    unresolved = tuple(sorted({*report.unresolved_risks, *("UNSET:" + s for s in missing)}))
    status = (
        "FAIL"
        if "FAIL" in checks.values()
        else "REQUIRES_REVIEW"
        if "UNSET" in checks.values() or unresolved
        else "PASS"
    )
    return report.model_copy(
        update={
            "gate_results": checks,
            "unresolved_risks": unresolved,
            "validation_status": status,
            "paper_eligibility": "NOT_ELIGIBLE"
            if status == "FAIL"
            else "REQUIRES_REVIEW"
            if status == "REQUIRES_REVIEW"
            else "ELIGIBLE_FOR_FORWARD_PAPER_VALIDATION",
        }
    )
