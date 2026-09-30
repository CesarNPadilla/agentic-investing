"""Shared historical/current strategy logic. Outputs are analysis and data only."""

from decimal import ROUND_FLOOR, Decimal

from portfolio.reconciliation import reconcile
from risk.evaluator import HypotheticalTrade, digest
from risk.proposals import ProposalDetails, create_trade_proposal
from strategies.models import StrategyEvaluation
from strategies.opportunities import research_gaps
from strategies.sizing import FixedNotionalSizer
from technical.indicators import TechnicalIndicatorService


def concentration(state, symbol, notional, fees):
    report = reconcile(state, state)
    if report.equity is None or report.equity <= fees or report.gross_exposure is None:
        return None, None
    current = report.per_symbol.get(symbol, Decimal(0))
    pending = Decimal(0)
    for order in state.open_orders:
        if order.side == "buy" and order.symbol == symbol:
            if order.limit_price is None:
                return None, None
            pending += (order.quantity - order.filled_quantity) * order.limit_price
    # Cash-funded purchases do not increase equity; fees decrease it.
    return current / report.equity, (current + pending + notional) / (report.equity - fees)


class _ResearchStrategy:
    """Shared evidence/sizing plumbing; subclasses supply distinct entry rules."""

    def evaluate(
        self, opportunity, assessment, thesis, state, policy, version, *, now, fees, history=None
    ):
        if version.strategy_domain != self.domain or opportunity.strategy_domain != self.domain:
            return StrategyEvaluation(status="REJECTED", reasons=("strategy_domain_mismatch",))
        if version.status == "RETIRED" or version.created_at > now:
            return StrategyEvaluation(status="REJECTED", reasons=("strategy_unavailable",))
        if opportunity.opportunity_status == "EXPIRED":
            return StrategyEvaluation(status="REJECTED", reasons=("opportunity_expired",))
        if (
            opportunity.assessment_digest != digest(assessment)
            or opportunity.thesis_reference != digest(thesis)
            or opportunity.research_assessment_id != assessment.assessment_id
            or opportunity.symbol != assessment.symbol
            or opportunity.timestamp > now
        ):
            return StrategyEvaluation(status="REJECTED", reasons=("research_binding_mismatch",))
        exit_reasons = self.exit_review(assessment, thesis, now)
        if exit_reasons:
            return StrategyEvaluation(status="EXIT_REVIEW", reasons=exit_reasons)
        if assessment.symbol not in policy.new_purchase_allowlist or not policy.may_research(
            assessment.symbol, state.positions
        ):
            return StrategyEvaluation(status="REJECTED", reasons=("purchase_not_authorized",))
        gaps = list(research_gaps(assessment, thesis, state, version.configuration, now))
        if not version.authorization_reference:
            gaps.append("strategy_authorization_UNSET")
        config = version.configuration
        if fees is None:
            gaps.append("fee_estimate")
        elif not fees.is_finite() or fees < 0:
            return StrategyEvaluation(status="REJECTED", reasons=("invalid_fees",))
        if config.valuation_decision == "UNSET" or config.portfolio_fit_decision == "UNSET":
            gaps.append("entry_decisions_unset")
        if gaps:
            return StrategyEvaluation(status="INSUFFICIENT_DATA", reasons=tuple(sorted(set(gaps))))
        if (
            config.valuation_decision != "ACCEPTABLE"
            or config.portfolio_fit_decision != "ACCEPTABLE"
            or thesis.thesis_status != "ACTIVE"
            or assessment.thesis_status not in {"STRONGER", "UNCHANGED"}
        ):
            return StrategyEvaluation(status="NO_ENTRY", reasons=("entry_framework_not_satisfied",))
        sizing = self.entry(assessment, version, history, now)
        if isinstance(sizing, StrategyEvaluation):
            return sizing
        if self.domain == "swing" and "SWING_ELIGIBLE" not in thesis.secondary_classifications:
            return StrategyEvaluation(status="NO_ENTRY", reasons=("swing_eligibility_unset",))
        notional, entry_logic, exit_logic = sizing
        quantity = FixedNotionalSizer().quantity(
            notional=notional, price=assessment.current_price, fees=fees, state=state, policy=policy
        )
        if quantity is None:
            return StrategyEvaluation(
                status="INSUFFICIENT_DATA", reasons=("bounded_size_unavailable",)
            )
        cost = quantity * assessment.current_price
        before, after = concentration(state, assessment.symbol, cost, fees)
        if before is None or after is None:
            return StrategyEvaluation(
                status="INSUFFICIENT_DATA", reasons=("concentration_unavailable",)
            )
        if config.concentration_ceiling is not None and after > config.concentration_ceiling:
            return StrategyEvaluation(status="NO_ENTRY", reasons=("concentration_ceiling",))
        trade = HypotheticalTrade(
            account_id=thesis.account_id,
            symbol=assessment.symbol,
            side="buy",
            quantity=quantity,
            limit_price=assessment.current_price,
            estimated_fees=fees,
            asset_type="equity",
            leverage_factor=1,
            thesis=assessment.investment_thesis,
            entry_thesis=entry_logic,
            exit_invalidation_thesis="; ".join(assessment.invalidation_conditions),
        )
        proposal = create_trade_proposal(
            policy,
            trade,
            ProposalDetails(
                strategy_id=version.strategy_id,
                strategy_version=version.strategy_version,
                strategy_configuration_digest=digest(version),
                strategy_domain=self.domain,
                opportunity_id=opportunity.opportunity_id,
                research_assessment_id=assessment.assessment_id,
                thesis_reference=digest(thesis),
                rationale=assessment.investment_thesis,
                catalysts=tuple(c.text for c in assessment.catalysts),
                risks=tuple(c.text for c in assessment.risks),
                expected_horizon="5-10+ years"
                if self.domain == "long_term"
                else f"Up to {version.swing.max_holding_sessions} sessions",
                proposed_holding_days=version.swing.max_holding_days
                if self.domain == "swing"
                else None,
                invalidation_condition="; ".join(assessment.invalidation_conditions),
                proposed_entry=entry_logic,
                proposed_exit_logic=exit_logic,
                portfolio_impact={
                    "fit": config.portfolio_fit_decision,
                    "valuation": config.valuation_decision,
                    "denominator": "whole portfolio equity; pending symbol buys included",
                    "opposing_factors": "; ".join(opportunity.opposing_factors),
                    "uncertainty": "; ".join(opportunity.uncertainty),
                },
                concentration_before=before,
                concentration_after=after,
                experimental_capital_required=cost + fees,
                data_timestamp=assessment.market_data_timestamp,
                supporting_data_references=(
                    f"assessment:{assessment.assessment_id}",
                    *opportunity.evidence_references,
                ),
                status="RISK_REVIEW",
            ),
            now=now,
        )
        return StrategyEvaluation(
            status="RISK_REVIEW", reasons=("entry_framework_satisfied",), proposal=proposal
        )

    def exit_review(self, assessment, thesis, now):
        reasons = []
        if (
            assessment.thesis_status in {"INVALIDATED", "WEAKER"}
            or thesis.thesis_status == "INVALIDATED"
        ):
            reasons.append("thesis_deterioration")
        if thesis.risk_flags or assessment.concentration_impact:
            reasons.append("concentration_review")
        sources = {s.source_id for s in assessment.data_sources}
        review_categories = {
            "fundamental_deterioration",
            "competitive_deterioration",
            "management_failure",
            "valuation_dislocation",
            "better_capital_allocation",
            "catalyst_completed",
            "structural_industry_change",
        }
        reasons.extend(
            e.category
            for e in thesis.material_events
            if e.category in review_categories
            and e.occurred_at <= now
            and e.source_reference in sources
        )
        # Material changes remain structured review inputs, never automatic sale triggers.
        return tuple(reasons)


class LongTermStrategy(_ResearchStrategy):
    domain = "long_term"

    def entry(self, assessment, version, history, now):
        if version.configuration.fixed_notional is None:
            return StrategyEvaluation(status="INSUFFICIENT_DATA", reasons=("fixed_notional_unset",))
        return (
            version.configuration.fixed_notional,
            "Cash-funded limit entry after durable thesis, valuation and portfolio review",
            (
                "EXIT_REVIEW on thesis invalidation, fundamental/competitive/management deterioration, "
                "valuation dislocation, superior capital allocation, concentration, catalyst completion "
                "or structural industry change; never automatic selling"
            ),
        )


class SwingStrategy(_ResearchStrategy):
    domain = "swing"

    def entry(self, assessment, version, history, now):
        config = version.swing
        required = (
            config.fast_period,
            config.slow_period,
            config.stop_atr_multiple,
            config.profit_atr_multiple,
            config.max_holding_sessions,
            config.max_holding_days,
            config.risk_budget,
            config.max_notional,
        )
        if config.parameters_status == "UNSET" or any(v is None for v in required):
            return StrategyEvaluation(
                status="INSUFFICIENT_DATA", reasons=("swing_parameters_UNSET",)
            )
        if config.fast_period < 2 or config.fast_period >= config.slow_period:
            return StrategyEvaluation(status="REJECTED", reasons=("swing_period_order",))
        if history is None or history.symbol != assessment.symbol:
            return StrategyEvaluation(status="INSUFFICIENT_DATA", reasons=("swing_history",))
        service = TechnicalIndicatorService()
        fast, slow = [
            service.calculate(
                history, as_of=now, period=p, allow_test_data=version.configuration.allow_test_data
            )
            for p in (config.fast_period, config.slow_period)
        ]
        if (
            fast.status != "AVAILABLE"
            or slow.status != "AVAILABLE"
            or not 0
            <= (now - fast.data_timestamp).total_seconds()
            <= version.configuration.max_research_age_seconds
        ):
            return StrategyEvaluation(status="INSUFFICIENT_DATA", reasons=("technical_quality",))
        if fast.values["sma"] <= slow.values["sma"] or slow.values["atr"] <= 0:
            return StrategyEvaluation(status="NO_ENTRY", reasons=("swing_entry_condition_false",))
        distance = config.stop_atr_multiple * slow.values["atr"]
        quantity = (config.risk_budget / distance).to_integral_value(rounding=ROUND_FLOOR)
        notional = min(config.max_notional, quantity * assessment.current_price)
        return (
            notional,
            f"Research SMA({config.fast_period}) > SMA({config.slow_period}); ATR-adjusted size",
            (
                f"Simulation exit: fast SMA <= slow SMA, entry minus {distance} stop, "
                f"entry plus {config.profit_atr_multiple * slow.values['atr']} profit target, "
                f"or {config.max_holding_sessions} sessions; no order submission"
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
        """Close-based simulation rules; no intrabar fill assumptions or sell proposals."""
        config = version.swing
        if (
            version.strategy_domain != self.domain
            or config.parameters_status == "UNSET"
            or any(
                v is None
                for v in (
                    config.stop_atr_multiple,
                    config.profit_atr_multiple,
                    config.max_holding_sessions,
                    config.max_holding_days,
                )
            )
        ):
            return StrategyEvaluation(
                status="INSUFFICIENT_DATA", reasons=("swing_parameters_UNSET",)
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
        if current_price <= entry_price - config.stop_atr_multiple * entry_atr:
            reasons.append("stop_loss")
        if current_price >= entry_price + config.profit_atr_multiple * entry_atr:
            reasons.append("profit_target")
        if fast_sma <= slow_sma:
            reasons.append("trend_exit")
        if held_sessions >= config.max_holding_sessions or held_days >= config.max_holding_days:
            reasons.append("maximum_holding_period")
        return StrategyEvaluation(
            status="EXIT_REVIEW" if reasons else "NO_ENTRY", reasons=tuple(reasons)
        )
