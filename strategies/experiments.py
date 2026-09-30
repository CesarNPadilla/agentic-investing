"""Two named hypotheses using shared proposals, sizing, indicators and risk review."""

from decimal import ROUND_FLOOR, Decimal

from portfolio.reconciliation import reconcile
from risk.policy import MAGNIFICENT_SEVEN
from strategies.engine import LongTermStrategy, SwingStrategy
from strategies.experiment_models import DimensionCheck
from strategies.models import StrategyEvaluation
from strategies.opportunities import research_gaps
from technical.indicators import TechnicalIndicatorService


def check(name, dimension, passed, requirement, observed=None, evidence=()):
    return DimensionCheck(
        name=name,
        dimension=dimension,
        status=passed if isinstance(passed, str) else "PASS" if passed else "FAIL",
        observed=str(observed) if observed is not None else None,
        requirement=requirement,
        evidence=tuple(evidence),
    )


def metric_check(rule, assessment, now):
    sources = {s.source_id: s for s in assessment.data_sources}
    candidates = [
        m
        for m in assessment.metrics
        if (m.name, m.unit, m.basis) == (rule.metric, rule.unit, rule.basis)
    ]
    usable = [
        m
        for m in candidates
        if m.source_id in sources
        and sources[m.source_id].reliable
        and sources[m.source_id].symbol == assessment.symbol
        and sources[m.source_id].published_at
        <= sources[m.source_id].retrieved_at
        <= assessment.timestamp
        <= now
        and (sources[m.source_id].period_start, sources[m.source_id].period_end)
        == (m.period_start, m.period_end)
    ]
    latest = max(usable, key=lambda m: (m.period_end, m.period_start)) if usable else None
    if (
        latest
        and sum(
            (m.period_start, m.period_end) == (latest.period_start, latest.period_end)
            for m in usable
        )
        > 1
    ):
        latest = None  # Ambiguous revisions need a provider-selected PIT observation.
    status = (
        "UNSET"
        if rule.threshold is None
        else "INSUFFICIENT_DATA"
        if latest is None
        else (
            "PASS"
            if (
                latest.value >= rule.threshold
                if rule.operator == "ge"
                else latest.value <= rule.threshold
            )
            else "FAIL"
        )
    )
    return check(
        rule.name,
        rule.dimension,
        status,
        f"{rule.metric} [{rule.unit}, {rule.basis}] {rule.operator} {rule.threshold if rule.threshold is not None else 'UNSET'}",
        latest.value if latest else None,
        (latest.source_id,) if latest else (),
    )


class ExperimentMixin:
    def evaluate(
        self,
        opportunity,
        assessment,
        thesis,
        state,
        policy,
        version,
        *,
        now,
        fees,
        history=None,
        historical_replay=False,
    ):
        diagnostics = self.diagnose(
            assessment, thesis, state, policy, version, now=now, history=history
        )
        exits = self.exit_review(assessment, thesis, now)
        if exits:
            return StrategyEvaluation(status="EXIT_REVIEW", reasons=exits, diagnostics=diagnostics)
        failures = [c for c in diagnostics if c.status in {"FAIL", "UNSET", "INSUFFICIENT_DATA"}]
        if failures:
            return StrategyEvaluation(
                status="INSUFFICIENT_DATA"
                if any(c.status in {"UNSET", "INSUFFICIENT_DATA"} for c in failures)
                else "NO_ENTRY",
                reasons=tuple(f"{c.name}:{c.status}" for c in failures),
                diagnostics=diagnostics,
            )
        result = super().evaluate(
            opportunity,
            assessment,
            thesis,
            state,
            policy,
            version,
            now=now,
            fees=fees,
            history=history,
            historical_replay=historical_replay,
        )
        return result.model_copy(update={"diagnostics": diagnostics})

    def common(self, assessment, thesis, state, policy, version, now):
        parameters = version.experiment
        gaps = research_gaps(assessment, thesis, state, version.configuration, now)
        report = reconcile(state, state)
        allocation = (
            report.per_symbol.get(assessment.symbol, Decimal(0)) / report.equity
            if report.equity
            else None
        )
        mag7 = sum(
            (value for symbol, value in report.per_symbol.items() if symbol in MAGNIFICENT_SEVEN),
            Decimal(0),
        )
        ceiling = version.configuration.concentration_ceiling
        return (
            check(
                "experiment_universe",
                "universe",
                assessment.symbol in parameters.permitted_symbols,
                "Exact security must be permitted; GOOG and GOOGL are separate instruments",
                assessment.symbol,
            ),
            check(
                "data_quality",
                "data_quality",
                "INSUFFICIENT_DATA" if gaps else "PASS",
                "Complete fresh research with source/thesis binding",
                "; ".join(gaps),
            ),
            check(
                "thesis",
                "thesis",
                thesis.thesis_status == "ACTIVE"
                and assessment.thesis_status in {"STRONGER", "UNCHANGED"},
                "Active supported thesis, no invalidation",
                assessment.thesis_status,
            ),
            check(
                "concentration",
                "portfolio_fit",
                "UNSET"
                if ceiling is None
                else "INSUFFICIENT_DATA"
                if allocation is None
                else allocation <= ceiling,
                f"Current and proposed equity allocation <= {ceiling if ceiling is not None else 'UNSET'}; proposed checked by shared strategy",
                allocation,
            ),
            check(
                "mag7_exposure",
                "portfolio_fit",
                "CONTEXT",
                "Direct holdings / total equity; no target ownership requirement",
                mag7 / report.equity if report.equity else None,
            ),
            check(
                "technology_exposure",
                "portfolio_fit",
                "CONTEXT",
                "UNAVAILABLE without trusted point-in-time sector references",
            ),
            check(
                "correlation_redundancy",
                "portfolio_fit",
                "CONTEXT",
                "UNAVAILABLE without aligned reliable correlation evidence",
            ),
            check(
                "existing_holdings",
                "portfolio_fit",
                "CONTEXT",
                "Existing holdings are context, not purchase permission",
                ",".join(sorted(report.per_symbol)),
            ),
            check(
                "purchase_permission",
                "policy",
                assessment.symbol in policy.new_purchase_allowlist,
                "Experiment universe does not alter InvestmentPolicy purchase permission",
                assessment.symbol,
            ),
        )


class LongTermQualityGrowthStrategy(ExperimentMixin, LongTermStrategy):
    def diagnose(self, assessment, thesis, state, policy, version, *, now, history=None):
        checks = list(self.common(assessment, thesis, state, policy, version, now))
        checks.extend(metric_check(r, assessment, now) for r in version.experiment.metric_rules)
        sources = {
            s.source_id for s in assessment.data_sources if s.reliable and s.retrieved_at <= now
        }
        for name, claims in (
            ("business_quality", assessment.competitive_position),
            ("growth_context", assessment.growth_context),
        ):
            valid = bool(claims) and all(set(c.evidence_references) <= sources for c in claims)
            checks.append(
                check(
                    name,
                    name,
                    "PASS" if valid else "INSUFFICIENT_DATA",
                    "Source-linked qualitative evidence; no numerical company score",
                    "; ".join(c.text for c in claims),
                    tuple(sorted(sources)),
                )
            )
        checks.append(
            check(
                "valuation",
                "valuation",
                "UNSET"
                if version.configuration.valuation_decision == "UNSET"
                else assessment.valuation_context.status == "AVAILABLE"
                and version.configuration.valuation_decision == "ACCEPTABLE",
                "At least one supported method/conclusion and explicit reviewed decision",
                assessment.valuation_context.status,
            )
        )
        checks.append(
            check(
                "portfolio_fit",
                "portfolio_fit",
                "UNSET"
                if version.configuration.portfolio_fit_decision == "UNSET"
                else version.configuration.portfolio_fit_decision == "ACCEPTABLE",
                "Explicit reviewed portfolio-fit decision",
                version.configuration.portfolio_fit_decision,
            )
        )
        return tuple(checks)

    def exit_review(self, assessment, thesis, now):
        reasons = list(super().exit_review(assessment, thesis, now))
        categories = {
            "sustained_fundamental_deterioration",
            "financial_health_deterioration",
            "valuation_fundamental_divergence",
            "catalyst_failure",
        }
        sources = {
            s.source_id for s in assessment.data_sources if s.reliable and s.retrieved_at <= now
        }
        reasons.extend(
            e.category
            for e in thesis.material_events
            if e.category in categories and e.occurred_at <= now and e.source_reference in sources
        )
        return tuple(sorted(set(reasons)))


class SwingTrendMomentumStrategy(ExperimentMixin, SwingStrategy):
    def technical_checks(self, history, version, now):
        p = version.experiment
        if history is None:
            return (
                check(
                    "technical_history",
                    "technical",
                    "INSUFFICIENT_DATA",
                    "PIT adjusted OHLCV required",
                ),
            )
        service = TechnicalIndicatorService()
        periods = {
            p.trend_period,
            p.intermediate_period,
            p.rsi_period,
            p.volume_period,
            p.atr_period,
        }
        snapshots = {
            period: service.calculate(
                history,
                as_of=now,
                period=period,
                allow_test_data=version.configuration.allow_test_data,
            )
            for period in periods
        }
        if any(s.status != "AVAILABLE" for s in snapshots.values()):
            return (
                check(
                    "technical_history",
                    "technical",
                    "INSUFFICIENT_DATA",
                    "All configured indicator windows must be available",
                    "; ".join(sorted({m for s in snapshots.values() for m in s.missing_data})),
                ),
            )
        bars = [b for b in history.bars if b.session_close <= now and b.available_at <= now]
        last = bars[-1]
        slow = snapshots[p.trend_period].values["sma"]
        fast = snapshots[p.intermediate_period].values["sma"]
        rsi = snapshots[p.rsi_period].values["rsi"]
        atr = snapshots[p.atr_period].values["atr"]
        # Excludes signal-day volume; compares with the prior N complete sessions.
        prior_volume = sum(b.volume for b in bars[-p.volume_period - 1 : -1]) / p.volume_period
        return (
            check(
                "technical_freshness",
                "technical",
                0
                <= (now - last.session_close).total_seconds()
                <= version.configuration.max_research_age_seconds,
                "Indicators must be fresh at the signal cutoff",
                last.session_close.isoformat(),
            ),
            check(
                "price_above_trend",
                "technical",
                last.close > slow,
                f"close > SMA({p.trend_period})={slow}",
                last.close,
            ),
            check(
                "intermediate_above_trend",
                "technical",
                fast > slow,
                f"SMA({p.intermediate_period}) > SMA({p.trend_period})={slow}",
                fast,
            ),
            check(
                "rsi_lower",
                "momentum",
                rsi > p.rsi_lower,
                f"RSI({p.rsi_period}) > {p.rsi_lower}",
                rsi,
            ),
            check(
                "rsi_upper",
                "momentum",
                rsi < p.rsi_upper,
                f"RSI({p.rsi_period}) < {p.rsi_upper}",
                rsi,
            ),
            check(
                "volume_confirmation",
                "volume",
                (last.volume > prior_volume > 0) if p.require_volume else "CONTEXT",
                f"Volume > prior {p.volume_period}-session mean {prior_volume}"
                if p.require_volume
                else "Volume filter explicitly disabled",
                last.volume,
            ),
            check("atr", "volatility", atr > 0, f"ATR({p.atr_period}) > 0", atr),
        )

    def diagnose(self, assessment, thesis, state, policy, version, *, now, history=None):
        checks = list(self.common(assessment, thesis, state, policy, version, now))
        checks.append(
            check(
                "history_symbol",
                "technical",
                history is not None and history.symbol == assessment.symbol,
                "Indicator history must describe the exact proposal security",
                history.symbol if history is not None else None,
            )
        )
        checks.extend(self.technical_checks(history, version, now))
        p = version.experiment
        checks.append(
            check(
                "exit_parameters",
                "risk",
                "UNSET"
                if any(
                    v is None
                    for v in (
                        p.atr_stop_multiple,
                        p.max_holding_sessions,
                        p.max_holding_days,
                        p.parameters_approved_reference,
                    )
                )
                else "PASS",
                "Explicit reviewed ATR/holding parameters required; research defaults are not approval",
            )
        )
        return tuple(checks)

    def entry(self, assessment, version, history, now):
        p, sizing = version.experiment, version.swing
        if sizing.risk_budget is None or sizing.max_notional is None or p.atr_stop_multiple is None:
            return StrategyEvaluation(
                status="INSUFFICIENT_DATA", reasons=("position_sizing_UNSET",)
            )
        atr = (
            TechnicalIndicatorService()
            .calculate(
                history,
                as_of=now,
                period=p.atr_period,
                allow_test_data=version.configuration.allow_test_data,
            )
            .values["atr"]
        )
        if atr is None or atr <= 0:
            return StrategyEvaluation(status="INSUFFICIENT_DATA", reasons=("atr_UNAVAILABLE",))
        quantity = (sizing.risk_budget / (p.atr_stop_multiple * atr)).to_integral_value(
            rounding=ROUND_FLOOR
        )
        notional = min(sizing.max_notional, quantity * assessment.current_price)
        # The shared evaluate method then uses FixedNotionalSizer and independent policy risk.
        return (
            notional,
            "Experimental close/SMA trend, RSI interval and prior-volume confirmation",
            (
                "EXIT_REVIEW on close below intermediate/trend SMA, configured holding limit or entry-ATR stop; no automatic sell"
            ),
        )

    def review_exit(
        self,
        version,
        *,
        entry_price,
        entry_atr,
        current_price,
        fast_sma,
        slow_sma,
        held_sessions,
        held_days,
    ):
        p = version.experiment
        if any(
            v is None for v in (p.atr_stop_multiple, p.max_holding_sessions, p.max_holding_days)
        ):
            return StrategyEvaluation(
                status="INSUFFICIENT_DATA", reasons=("exit_parameters_UNSET",)
            )
        if (
            any(
                not v.is_finite() or v <= 0
                for v in (entry_price, entry_atr, current_price, fast_sma, slow_sma)
            )
            or min(held_sessions, held_days) < 0
        ):
            return StrategyEvaluation(status="INSUFFICIENT_DATA", reasons=("invalid_exit_inputs",))
        reasons = []
        if current_price < fast_sma:
            reasons.append("intermediate_trend_exit")
        if current_price <= slow_sma or fast_sma <= slow_sma:
            reasons.append("trend_filter_failed")
        if current_price <= entry_price - p.atr_stop_multiple * entry_atr:
            reasons.append("atr_stop_review")
        if held_sessions >= p.max_holding_sessions or held_days >= p.max_holding_days:
            reasons.append("maximum_holding_period")
        return StrategyEvaluation(
            status="EXIT_REVIEW" if reasons else "NO_ENTRY", reasons=tuple(reasons)
        )
