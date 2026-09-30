"""Research proposals are evidence only, with no execution/service integration."""

from datetime import UTC, datetime
from decimal import Decimal
from typing import Literal
from uuid import uuid4

from pydantic import AwareDatetime, Field

from portfolio.state import Record
from risk.evaluator import HypotheticalTrade, digest
from risk.policy import InvestmentPolicy


class OpportunityProposalFields(Record):
    strategy_version: str | None = None
    strategy_configuration_digest: str | None = None
    opportunity_id: str | None = None
    research_assessment_id: str | None = None
    concentration_before: Decimal | None = None
    concentration_after: Decimal | None = None
    experimental_capital_required: Decimal | None = None
    data_timestamp: AwareDatetime | None = None
    status: Literal[
        "DRAFT", "RISK_REVIEW", "REJECTED", "HUMAN_REVIEW", "APPROVED_FOR_PAPER", "EXPIRED"
    ] = "DRAFT"


class TradeProposal(OpportunityProposalFields):
    proposal_id: str
    timestamp: AwareDatetime
    proposal_digest: str
    policy_digest: str
    trade: HypotheticalTrade
    strategy_id: str | None = None
    strategy_domain: Literal["long_term", "swing"] | None = None
    thesis_reference: str | None = None
    rationale: str | None = None
    catalysts: tuple[str, ...] | None = None
    risks: tuple[str, ...] | None = None
    expected_horizon: str | None = None
    proposed_holding_days: int | None = Field(default=None, gt=0)
    invalidation_condition: str | None = None
    portfolio_impact: dict[str, str] | None = None
    proposed_entry: str | None = None
    proposed_exit_logic: str | None = None
    confidence: float | None = Field(default=None, ge=0, le=1, allow_inf_nan=False)
    confidence_method: str | None = None
    supporting_data_references: tuple[str, ...] = ()
    execution_available: Literal[False] = False


class ProposalDetails(OpportunityProposalFields):
    strategy_id: str | None = None
    strategy_domain: Literal["long_term", "swing"] | None = None
    thesis_reference: str | None = None
    rationale: str | None = None
    catalysts: tuple[str, ...] | None = None
    risks: tuple[str, ...] | None = None
    expected_horizon: str | None = None
    proposed_holding_days: int | None = Field(default=None, gt=0)
    invalidation_condition: str | None = None
    portfolio_impact: dict[str, str] | None = None
    proposed_entry: str | None = None
    proposed_exit_logic: str | None = None
    confidence: float | None = Field(default=None, ge=0, le=1, allow_inf_nan=False)
    confidence_method: str | None = None
    supporting_data_references: tuple[str, ...] = ()


def proposal_binding_valid(proposal: TradeProposal) -> bool:
    """Read old research proposals without changing their original digest contract."""
    payload = proposal.model_dump(exclude={"proposal_digest"})
    if proposal.proposal_digest == digest(payload):
        return True
    defaults = OpportunityProposalFields().model_dump()
    if any(payload[name] != default for name, default in defaults.items()):
        return False
    legacy = {name: value for name, value in payload.items() if name not in defaults}
    return proposal.proposal_digest == digest(legacy)


def create_trade_proposal(
    policy: InvestmentPolicy,
    trade: HypotheticalTrade,
    details: ProposalDetails | None = None,
    *,
    now: datetime | None = None,
) -> TradeProposal:
    """Agent-facing factory; holdings and research permission grant no BUY permission."""
    if trade.side != "buy" or trade.symbol not in policy.new_purchase_allowlist:
        raise ValueError("New BUY proposal is outside the purchase allowlist")
    if any(
        not value or not value.strip()
        for value in (trade.thesis, trade.entry_thesis, trade.exit_invalidation_thesis)
    ):
        raise ValueError("Proposal requires ownership, entry and invalidation theses")
    payload = dict(
        proposal_id=str(uuid4()),
        timestamp=now or datetime.now(UTC),
        policy_digest=digest(policy),
        trade=trade,
        execution_available=False,
        **(details or ProposalDetails()).model_dump(),
    )
    return TradeProposal(proposal_digest=digest(payload), **payload)
