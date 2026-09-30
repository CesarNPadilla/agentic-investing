"""Structured research and thesis inputs only; no headline-to-proposal shortcut."""

from datetime import datetime
from uuid import uuid4

from agents.long_term.analysis import source_freshness
from agents.long_term.models import ResearchAssessment
from portfolio.state import PortfolioState
from portfolio.theses import PositionThesis
from risk.evaluator import digest
from risk.policy import InvestmentPolicy
from strategies.models import EntryConfig, InvestmentOpportunity


def research_gaps(assessment, thesis, state, config, now):
    if now.tzinfo is None or now.utcoffset() is None:
        raise ValueError("Aware evaluation time required")
    gaps = list(assessment.missing_data)
    for label, stamp in (
        ("assessment", assessment.timestamp),
        ("market", assessment.market_data_timestamp),
        ("portfolio", state.as_of),
    ):
        if (
            stamp is None
            or not 0 <= (now - stamp).total_seconds() <= config.max_research_age_seconds
        ):
            gaps.append(label + "_freshness")
    if not assessment.data_quality or any(
        q.state not in {"CURRENT", "LATEST_REPORTED"} or q.as_of is None or q.as_of > now
        for q in assessment.data_quality.values()
    ):
        gaps.append("data_quality")
    if not {"market", "fundamentals", "portfolio"} <= assessment.data_quality.keys():
        gaps.append("required_quality_dimensions")
    sources = {s.source_id: s for s in assessment.data_sources}
    if len(sources) < config.min_evidence_sources or len(sources) != len(assessment.data_sources):
        gaps.append("evidence_sources")
    if any(
        not s.reliable
        or (s.is_sample and not config.allow_test_data)
        or s.symbol != assessment.symbol
        or s.retrieved_at > assessment.timestamp
        or s.historical
        for s in sources.values()
    ):
        gaps.append("source_provenance")
    freshness_config = config.source_freshness.model_copy(
        update={"allow_test_data": config.allow_test_data}
    )
    if any(
        source_freshness(s, now, freshness_config).state != "LATEST_REPORTED"
        for s in sources.values()
    ):
        gaps.append("source_freshness")
    if assessment.fundamental_data_timestamp is None:
        gaps.append("fundamentals_timestamp")
    if any(
        stamp is not None and stamp > assessment.timestamp
        for stamp in (assessment.market_data_timestamp, assessment.fundamental_data_timestamp)
    ):
        gaps.append("incompatible_timestamps")
    claims = (
        *assessment.positive_drivers,
        *assessment.negative_drivers,
        *assessment.risks,
        *assessment.catalysts,
        *assessment.valuation_context.conclusions,
    )
    if any(not set(c.evidence_references) <= sources.keys() for c in claims):
        gaps.append("unresolved_evidence")
    if not assessment.investment_thesis or not assessment.positive_drivers:
        gaps.append("investment_rationale")
    if not assessment.risks or not assessment.invalidation_conditions:
        gaps.append("risks_or_invalidation")
    if not thesis.current_thesis or thesis.symbol != assessment.symbol:
        gaps.append("thesis_binding")
    if not any(
        r.review_id == assessment.assessment_id
        and r.reviewed_at == assessment.timestamp
        and r.assessment == assessment.thesis_status
        for r in thesis.agent_review_history
    ):
        gaps.append("assessment_thesis_review_binding")
    if thesis.last_review_date is None or thesis.last_review_date > now:
        gaps.append("thesis_review_time")
    if assessment.thesis_status == "INSUFFICIENT_DATA":
        gaps.append("thesis_assessment")
    if assessment.valuation_context.status != "AVAILABLE" or not (
        assessment.valuation_context.methods or assessment.valuation_context.conclusions
    ):
        gaps.append("valuation")
    if (
        assessment.current_price is None
        or not assessment.current_price.is_finite()
        or assessment.current_price <= 0
        or assessment.price_currency != "USD"
    ):
        gaps.append("price")
    if assessment.quote is not None and (
        assessment.quote.symbol != assessment.symbol
        or assessment.quote.price != assessment.current_price
        or assessment.quote.as_of != assessment.market_data_timestamp
        or (assessment.quote.is_sample and not config.allow_test_data)
    ):
        gaps.append("quote_consistency")
    context = assessment.portfolio_fit
    if context is None or context.as_of != state.as_of or context.data_gaps:
        gaps.append("portfolio_context")
    if (
        not state.positions_complete
        or not state.accounts_complete
        or not state.orders_complete
        or state.data_gaps
    ):
        gaps.append("portfolio_completeness")
    if not state.coherent_cutoff:
        gaps.append("incoherent_portfolio")
    if any(
        p.marked_value is None
        or p.price_as_of is None
        or not 0 <= (now - p.price_as_of).total_seconds() <= config.max_research_age_seconds
        for p in state.positions
    ):
        gaps.append("portfolio_marks")
    return tuple(sorted(set(gaps)))


class OpportunityEngine:
    def identify(
        self,
        assessment: ResearchAssessment,
        thesis: PositionThesis,
        state: PortfolioState,
        policy: InvestmentPolicy,
        config: EntryConfig,
        *,
        now: datetime,
        domain="long_term",
    ) -> InvestmentOpportunity:
        if not isinstance(assessment, ResearchAssessment):
            raise TypeError("ResearchAssessment required")
        gaps = research_gaps(assessment, thesis, state, config, now)
        holding = any(p.symbol == assessment.symbol and p.quantity > 0 for p in state.positions)
        authorized = assessment.symbol in policy.new_purchase_allowlist
        research_allowed = policy.may_research(assessment.symbol, state.positions)
        roles = ["existing_holding" if holding else "research_only"]
        if authorized:
            roles.append("new_purchase_candidate")
        if thesis.classification == "LEGACY_POSITION":
            roles.append("legacy_position")
        if "SWING_ELIGIBLE" in thesis.secondary_classifications:
            roles.append("swing_eligible")
        kinds = [
            "SWING_SETUP"
            if domain == "swing"
            else "ADD_TO_EXISTING"
            if holding
            else "NEW_LONG_TERM_POSITION"
        ]
        if assessment.thesis_status == "STRONGER":
            kinds.append("THESIS_STRENGTHENING")
        if assessment.thesis_status in {"WEAKER", "INVALIDATED"}:
            kinds.append("THESIS_WEAKENING")
        if thesis.thesis_status == "INVALIDATED" or assessment.thesis_status == "INVALIDATED":
            kinds.append("RISK_REDUCTION_REVIEW")
        if assessment.concentration_impact or thesis.risk_flags:
            kinds.append("CONCENTRATION_REVIEW")
        if config.valuation_decision != "ACCEPTABLE":
            kinds.append("VALUATION_REVIEW")
        if assessment.catalysts:
            kinds.append("CATALYST_EVENT")
        status = "IDENTIFIED"
        if not authorized or not research_allowed:
            status = "REJECTED"
        elif gaps:
            status = "INSUFFICIENT_DATA"
        elif thesis.thesis_status != "ACTIVE" or assessment.thesis_status not in {
            "STRONGER",
            "UNCHANGED",
        }:
            status = "UNDER_REVIEW"
        elif (
            config.valuation_decision == "ACCEPTABLE"
            and config.portfolio_fit_decision == "ACCEPTABLE"
        ):
            status = "STRATEGY_ELIGIBLE"
        return InvestmentOpportunity(
            opportunity_id=str(uuid4()),
            scope_id=assessment.scope_id,
            symbol=assessment.symbol,
            timestamp=now,
            opportunity_type=kinds[0],
            classifications=tuple(kinds),
            strategy_domain=domain,
            research_assessment_id=assessment.assessment_id,
            assessment_digest=digest(assessment),
            thesis_reference=digest(thesis),
            thesis_status=assessment.thesis_status,
            portfolio_role=assessment.portfolio_role,
            security_roles=tuple(roles),
            current_allocation=(
                assessment.portfolio_fit.current_allocation if assessment.portfolio_fit else None
            ),
            opportunity_summary=assessment.agent_summary,
            supporting_factors=tuple(c.text for c in assessment.positive_drivers),
            opposing_factors=tuple(c.text for c in assessment.negative_drivers),
            catalysts=tuple(c.text for c in assessment.catalysts),
            risks=tuple(c.text for c in assessment.risks),
            valuation_context=assessment.valuation_context,
            portfolio_fit=config.portfolio_fit_decision,
            concentration_impact=assessment.concentration_impact,
            investment_horizon="5-10+ years"
            if domain == "long_term"
            else "Configured trading sessions",
            data_quality=assessment.data_quality,
            missing_data=gaps,
            evidence_references=tuple(
                sorted(sources_id for sources_id in {s.source_id for s in assessment.data_sources})
            ),
            uncertainty=assessment.uncertainty,
            policy_checks=(
                f"purchase_authorized:{authorized}",
                f"research_authorized:{research_allowed}",
            ),
            opportunity_status=status,
        )
