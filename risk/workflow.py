"""Research -> Thesis -> Strategy -> Proposal -> Risk -> Human review. No broker calls."""

import json
import logging
from datetime import datetime
from typing import Literal, Protocol

from pydantic import Field

from portfolio.intelligence import experimental_utilization
from portfolio.state import PortfolioState, Record
from portfolio.theses import PositionThesis
from risk.evaluator import KillSwitch, RiskEvaluation, digest, evaluate
from risk.policy import InvestmentPolicy
from risk.proposals import TradeProposal

logger = logging.getLogger("investment_policy.audit")


class StrategyContext(Record):
    portfolio: PortfolioState
    thesis: PositionThesis
    research_references: tuple[str, ...]


class LongTermStrategy(Protocol):
    strategy_id: str
    domain: Literal["long_term"]

    def propose(self, context: StrategyContext) -> TradeProposal | None: ...


class SwingStrategy(Protocol):
    strategy_id: str
    domain: Literal["swing"]

    def propose(self, context: StrategyContext) -> TradeProposal | None: ...


class StrategyValidation(Record):
    strategy_id: str
    backtest_reference: str | None = None
    forward_paper_reference: str | None = None
    sequential_non_synthetic_sessions: int = Field(default=0, ge=0)
    bias_checks_passed: bool = False
    risk_review_passed: bool = False
    performance_review_passed: bool = False


class ProposalReview(Record):
    status: Literal["PASS", "REJECT", "REQUIRE_HUMAN_REVIEW", "INSUFFICIENT_DATA"]
    proposal: TradeProposal
    risk: RiskEvaluation
    reasons: tuple[str, ...]
    thesis_digest: str | None
    human_approval_required: Literal[True] = True
    execution_available: Literal[False] = False


def review_proposal(
    policy: InvestmentPolicy,
    opening: PortfolioState,
    closing: PortfolioState,
    proposal: TradeProposal,
    kill_switch: KillSwitch,
    thesis: PositionThesis | None,
    *,
    now: datetime,
    validation: StrategyValidation | None = None,
) -> ProposalReview:
    # Independently evaluate even if confidence is high or strategy labels itself approved.
    risk = evaluate(policy, opening, closing, proposal.trade, kill_switch, now=now)
    rejected, missing = [], []
    if proposal.policy_digest != digest(policy) or proposal.proposal_digest != digest(
        proposal.model_dump(exclude={"proposal_digest"})
    ):
        rejected.append("proposal_or_policy_binding_mismatch")
    if proposal.timestamp > now:
        rejected.append("future_proposal")
    if (
        policy.max_state_age_seconds is None
        or (now - proposal.timestamp).total_seconds() > policy.max_state_age_seconds
    ):
        missing.append("proposal_freshness_unverified")
    if (
        any(
            not getattr(proposal, field)
            for field in (
                "strategy_id",
                "strategy_domain",
                "thesis_reference",
                "rationale",
                "expected_horizon",
                "invalidation_condition",
                "proposed_entry",
                "proposed_exit_logic",
                "supporting_data_references",
            )
        )
        or proposal.risks is None
        or proposal.catalysts is None
    ):
        missing.append("proposal_research_metadata_missing")
    if thesis is None or not thesis.current_thesis or thesis.thesis_status != "ACTIVE":
        missing.append("active_current_thesis_required")
    elif (
        thesis.account_id != proposal.trade.account_id
        or thesis.symbol != proposal.trade.symbol
        or proposal.thesis_reference != digest(thesis)
    ):
        rejected.append("thesis_binding_mismatch")
    if proposal.strategy_domain == "swing":
        controls = policy.swing_controls
        if (
            any(
                getattr(controls, field) is None
                for field in ("max_position_capital", "max_loss", "max_holding_days", "stop_rule")
            )
            or not controls.stop_rule
        ):
            missing.append("swing_controls_unset")
        else:
            if (
                policy.agent_experimental_capital_limit is None
                or policy.max_experimental_loss is None
            ):
                missing.append("parent_risk_controls_unset")
            elif (
                controls.max_position_capital >= policy.agent_experimental_capital_limit
                or controls.max_loss >= policy.max_experimental_loss
            ):
                rejected.append("swing_controls_not_stricter")
            cost = proposal.trade.quantity * proposal.trade.limit_price
            if proposal.trade.estimated_fees is not None:
                cost += proposal.trade.estimated_fees
            if cost > controls.max_position_capital:
                rejected.append("swing_position_limit")
            sleeve = experimental_utilization(closing, policy)
            if not sleeve.valid or "unknown" in sleeve.strategy_attribution:
                missing.append("swing_strategy_attribution_missing")
            elif (
                cost + sleeve.strategy_attribution.get(proposal.strategy_id, 0)
                > controls.max_position_capital
            ):
                rejected.append("swing_strategy_capital_limit")
            if proposal.proposed_holding_days is None:
                missing.append("swing_holding_period_missing")
            elif proposal.proposed_holding_days > controls.max_holding_days:
                rejected.append("swing_holding_period_limit")
            pnl = (closing.experimental_strategy_pnl or {}).get(proposal.strategy_id)
            if pnl is None:
                missing.append("swing_loss_evidence_missing")
            elif -pnl >= controls.max_loss:
                rejected.append("swing_loss_stop")
        if (
            validation is None
            or validation.strategy_id != proposal.strategy_id
            or not validation.backtest_reference
            or not validation.forward_paper_reference
            or validation.sequential_non_synthetic_sessions < 60
            or not validation.bias_checks_passed
            or not validation.risk_review_passed
            or not validation.performance_review_passed
        ):
            missing.append("swing_validation_incomplete")
    status = (
        "REJECT"
        if rejected or risk.status == "REJECT"
        else "INSUFFICIENT_DATA"
        if missing or risk.status == "INSUFFICIENT_DATA"
        else "REQUIRE_HUMAN_REVIEW"
    )
    result = ProposalReview(
        status=status,
        proposal=proposal,
        risk=risk,
        reasons=tuple(rejected + missing),
        thesis_digest=digest(thesis) if thesis else None,
    )
    logger.info(
        json.dumps(
            {
                "event": "proposal_risk_review",
                "proposal_digest": proposal.proposal_digest,
                "status": status,
                "reasons": result.reasons,
                "human_approval_required": True,
                "execution_available": False,
            }
        )
    )
    return result


def review_strategy_output(
    strategy: LongTermStrategy | SwingStrategy,
    context: StrategyContext,
    policy: InvestmentPolicy,
    opening: PortfolioState,
    kill_switch: KillSwitch,
    *,
    now: datetime,
    validation: StrategyValidation | None = None,
):
    """Every strategy output enters risk; this facade exposes no execute operation."""
    proposal = strategy.propose(context)
    if proposal is None:
        return None
    if proposal.strategy_id != strategy.strategy_id or proposal.strategy_domain != strategy.domain:
        raise ValueError("Strategy identity/domain mismatch")
    return review_proposal(
        policy,
        opening,
        context.portfolio,
        proposal,
        kill_switch,
        context.thesis,
        now=now,
        validation=validation,
    )
