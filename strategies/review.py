"""Independent proposal checks plus existing deterministic policy risk controls."""

from risk.evaluator import digest
from risk.workflow import ProposalReview, review_proposal
from strategies.dispatch import strategy_for


def review_strategy_proposal(
    policy,
    opening,
    state,
    proposal,
    kill_switch,
    thesis,
    opportunity,
    assessment,
    version,
    *,
    now,
    history=None,
    validation=None,
    historical_replay=False,
):
    base = review_proposal(
        policy,
        opening,
        state,
        proposal,
        kill_switch,
        thesis,
        now=now,
        validation=validation,
        strategy_evidence_verified=True,
    )
    reasons = list(base.reasons)
    implementation = strategy_for(version)
    replay = implementation.evaluate(
        opportunity,
        assessment,
        thesis,
        state,
        policy,
        version,
        now=now,
        fees=proposal.trade.estimated_fees,
        history=history,
        historical_replay=historical_replay,
    )
    # Recompute strategy decisions; an LLM or caller cannot self-assert eligibility.
    excluded = {"proposal_id", "proposal_digest", "timestamp", "confidence", "confidence_method"}
    if replay.proposal is None or digest(replay.proposal.model_dump(exclude=excluded)) != digest(
        proposal.model_dump(exclude=excluded)
    ):
        reasons.append("strategy_replay_mismatch")
    if (
        proposal.opportunity_id != opportunity.opportunity_id
        or proposal.research_assessment_id != assessment.assessment_id
        or proposal.strategy_configuration_digest != digest(version)
        or proposal.strategy_version != version.strategy_version
    ):
        reasons.append("strategy_provenance_mismatch")
    status = "REJECT" if len(reasons) > len(base.reasons) else base.status
    return ProposalReview(
        status=status,
        proposal=proposal,
        risk=base.risk,
        reasons=tuple(reasons),
        thesis_digest=digest(thesis),
    )
