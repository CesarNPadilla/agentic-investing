"""Pure evidence evaluation. Cost basis and headlines are not thesis inputs."""

from datetime import timedelta

from agents.long_term.models import Claim, Freshness, PortfolioContext


def source_freshness(source, now, config):
    if source.retrieved_at > now or source.published_at > now:
        return Freshness(state="UNAVAILABLE", as_of=source.published_at, reason="future_source")
    if not source.reliable or (source.is_sample and not config.allow_test_data):
        return Freshness(
            state="UNAVAILABLE", as_of=source.published_at, reason="unverified_or_sample"
        )
    if source.historical:
        return Freshness(state="HISTORICAL", as_of=source.published_at)
    stale = now - source.retrieved_at > timedelta(days=config.retrieval_max_age_days)
    if source.period_end:
        stale |= (now.date() - source.period_end).days > config.financial_period_max_age_days
    else:
        stale |= now - source.published_at > timedelta(days=config.financial_period_max_age_days)
    return Freshness(
        state="STALE" if stale else "LATEST_REPORTED",
        as_of=source.published_at,
        reason="check_for_newer_evidence" if stale else None,
    )


def evaluate_assumptions(plan, metrics, previous):
    if plan is None:
        return "INSUFFICIENT_DATA", {}, (), (), ("reviewed_research_plan",)
    results, positives, negatives, gaps = {}, [], [], []
    selected = {}
    for assumption in plan.assumptions:
        candidates = [
            m
            for m in metrics
            if (m.name, m.unit, m.basis) == (assumption.metric, assumption.unit, assumption.basis)
        ]
        if candidates:
            newest = max(m.period_end for m in candidates)
            latest = [m for m in candidates if m.period_end == newest]
            if len(latest) == 1:
                selected[assumption.name] = latest[0]
    periods_by_basis = {}
    for metric in selected.values():
        periods_by_basis.setdefault(metric.basis, set()).add(
            (metric.period_start, metric.period_end)
        )
    incompatible = {basis for basis, periods in periods_by_basis.items() if len(periods) > 1}
    for assumption in plan.assumptions:
        metric = selected.get(assumption.name)
        if metric is None or metric.basis in incompatible:
            results[assumption.name] = None
            gaps.append("assumption:" + assumption.name)
            if metric is not None:
                gaps.append("incompatible_assumption_periods:" + metric.basis)
            continue
        result = (
            metric.value >= assumption.threshold
            if assumption.operator == "ge"
            else metric.value <= assumption.threshold
        )
        results[assumption.name] = result
        claim = Claim(
            text=f"{assumption.name}: {metric.name} {metric.value} {metric.unit}; "
            f"reviewed condition {assumption.operator} {assumption.threshold} is {result}",
            evidence_references=(metric.source_id,),
            kind="interpretation",
        )
        (positives if result else negatives).append(claim)
    if any(a.invalidates_when_false and results[a.name] is False for a in plan.assumptions):
        status = "INVALIDATED"
    elif gaps:
        status = "INSUFFICIENT_DATA"
    elif (
        not previous
        or previous.plan != plan
        or any(v is None for v in previous.assumption_results.values())
    ):
        status = "UNDER_REVIEW"  # Establish baseline, not a claim of improvement.
    else:
        improved = any(
            v is True and previous.assumption_results.get(k) is False for k, v in results.items()
        )
        weakened = any(
            v is False and previous.assumption_results.get(k) is True for k, v in results.items()
        )
        status = (
            "UNDER_REVIEW"
            if improved and weakened
            else "STRONGER"
            if improved
            else "WEAKER"
            if weakened
            else "UNCHANGED"
        )
        if previous.thesis_status == "INVALIDATED" and status != "INVALIDATED":
            status = "UNDER_REVIEW"  # Recovery needs an explicit reviewed thesis.
    return status, results, tuple(positives), tuple(negatives), tuple(gaps)


def portfolio_context(observation, symbol, canonical, theses):
    if observation is None:
        return None
    positions = [p for p in observation.state.portfolio_holdings if canonical(p.symbol) == symbol]
    allocations = [
        a for a in observation.intelligence.allocation_by_security if canonical(a.symbol) == symbol
    ]
    values = [p.marked_value for p in positions]
    bases = [p.cost_basis for p in positions]
    supported = (
        observation.state.positions_complete
        and observation.state.accounts_complete
        and all(p.currency == "USD" and p.quantity >= 0 for p in positions)
    )
    value = sum(values) if supported and all(v is not None for v in values) else None
    basis = sum(bases) if supported and all(v is not None for v in bases) else None
    allocation = (
        sum(a.allocation for a in allocations)
        if allocations and all(a.allocation is not None for a in allocations)
        else None
    )
    flags = {flag for t in theses for flag in t.thesis.risk_flags}
    flags.update(a.warning for a in allocations if a.warning)
    return PortfolioContext(
        observation_id=observation.id,
        as_of=observation.state.as_of,
        actual_symbols=tuple(sorted({p.symbol for p in positions})),
        current_allocation=allocation,
        current_market_value=value,
        cost_basis=basis,
        unrealized_pnl=value - basis if value is not None and basis is not None else None,
        classifications=tuple(sorted({t.thesis.classification for t in theses})),
        concentration_flags=tuple(sorted(flags)),
        data_gaps=observation.intelligence.data_gaps,
    )
