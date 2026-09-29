"""Research proposals are evidence only, with no execution/service integration."""

from typing import Literal

from portfolio.state import Record
from risk.evaluator import HypotheticalTrade, digest
from risk.policy import InvestmentPolicy


class TradeProposal(Record):
    proposal_digest: str
    policy_digest: str
    trade: HypotheticalTrade
    execution_available: Literal[False] = False


def create_trade_proposal(policy: InvestmentPolicy, trade: HypotheticalTrade) -> TradeProposal:
    """Agent-facing factory; holdings and research permission grant no BUY permission."""
    if trade.side != "buy" or trade.symbol not in policy.new_purchase_allowlist:
        raise ValueError("New BUY proposal is outside the purchase allowlist")
    if any(
        not value or not value.strip()
        for value in (trade.thesis, trade.entry_thesis, trade.exit_invalidation_thesis)
    ):
        raise ValueError("Proposal requires ownership, entry and invalidation theses")
    return TradeProposal(
        proposal_digest=digest((policy, trade)), policy_digest=digest(policy), trade=trade
    )
