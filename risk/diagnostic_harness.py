"""Offline, deterministic diagnostics around the existing hypothetical evaluator.

This module has no broker dependency or order submission capability.
"""

from datetime import datetime
from decimal import Decimal
from typing import Literal

from pydantic import AwareDatetime

from portfolio.reconciliation import reconcile
from portfolio.state import PortfolioState, Record
from risk.evaluator import HypotheticalTrade, KillSwitch, digest, evaluate
from risk.policy import InvestmentPolicy


class DiagnosticInput(Record):
    environment: Literal["research", "paper", "production"]
    policy: InvestmentPolicy | None
    opening: PortfolioState | None
    state: PortfolioState | None
    trade: HypotheticalTrade | None
    kill_switch: KillSwitch | None
    evaluated_at: AwareDatetime
    market_data_at: AwareDatetime | None
    core_session_open: bool | None
    proposal_id: str
    existing_proposal_ids: tuple[str, ...] = ()
    technical_eligibility: Literal["ELIGIBLE", "INELIGIBLE", "UNKNOWN"] = "UNKNOWN"
    proposed_capital_scenario: Decimal | None = None


class DiagnosticResult(Record):
    version: Literal["risk-diagnostic-v09"] = "risk-diagnostic-v09"
    decision: Literal["ALLOW", "REJECT", "REVIEW_REQUIRED"]
    reason_codes: tuple[str, ...]
    failed_controls: tuple[str, ...]
    missing_evidence: tuple[str, ...]
    policy_version: str | None
    policy_digest: str | None
    input_snapshot_digest: str
    audit_id: str
    evaluated_at: AwareDatetime
    pre_proposal_exposure: Decimal | None
    post_proposal_exposure: Decimal | None
    pre_concentration: Decimal | None
    post_concentration: Decimal | None
    cash_before_reservations: Decimal | None
    cash_after_reservations_and_proposal: Decimal | None
    proposed_capital_scenario: Decimal | None
    proposed_capital_is_authorized: Literal[False] = False
    technical_eligibility: Literal["ELIGIBLE", "INELIGIBLE", "UNKNOWN"]
    execution_available: Literal[False] = False


def diagnose(item: DiagnosticInput) -> DiagnosticResult:
    """Evaluate one explicit snapshot. Missing evidence blocks; a pass still needs human review."""
    now: datetime = item.evaluated_at
    snapshot_digest = digest(item)
    failed: list[str] = []
    missing: list[str] = []

    if item.policy is None:
        missing.append("missing_policy")
    if item.opening is None or item.state is None:
        missing.append("missing_portfolio_state")
    if item.trade is None:
        missing.append("missing_proposal")
    if item.kill_switch is None:
        missing.append("missing_kill_switch")
    if item.market_data_at is None or item.trade is None:
        missing.append("missing_market_price")
    elif item.policy is None or item.policy.max_state_age_seconds is None:
        missing.append("missing_market_age_limit")
    elif not 0 <= (now - item.market_data_at).total_seconds() <= item.policy.max_state_age_seconds:
        failed.append("stale_market_price")
    if item.core_session_open is None:
        missing.append("missing_session_state")
    elif not item.core_session_open:
        failed.append("session_closed")
    if item.proposal_id in item.existing_proposal_ids:
        failed.append("duplicate_proposal")
    if item.environment != "research":
        failed.append("diagnostic_environment")
    if item.state is not None and item.state.environment != item.environment:
        failed.append("environment_mismatch")
    if item.technical_eligibility == "INELIGIBLE":
        failed.append("technically_ineligible")

    report = reconcile(item.opening, item.state) if item.opening and item.state else None
    before = report.gross_exposure if report else None
    before_concentration = report.concentration if report else None
    cash = None
    cash_after = None
    if item.state and item.trade:
        account = next(
            (a for a in item.state.accounts if a.account_id == item.trade.account_id), None
        )
        if account and account.settled_cash is not None:
            cash = account.settled_cash
            pending = Decimal(0)
            for order in item.state.open_orders:
                if order.account_id == account.account_id and order.side == "buy":
                    if order.limit_price is None or order.remaining_fees is None:
                        pending = None
                        break
                    pending += (order.quantity - order.filled_quantity) * order.limit_price
                    pending += order.remaining_fees
            if pending is not None and item.trade.estimated_fees is not None:
                cash_after = cash - pending - item.trade.quantity * item.trade.limit_price
                cash_after -= item.trade.estimated_fees

    evaluation = None
    if all((item.policy, item.opening, item.state, item.trade, item.kill_switch)):
        evaluation = evaluate(
            item.policy, item.opening, item.state, item.trade, item.kill_switch, now=now
        )
        failed.extend(check.code for check in evaluation.checks if not check.passed)
        if evaluation.status == "INSUFFICIENT_DATA":
            missing.extend(
                check.code for check in evaluation.checks
                if not check.passed and (
                    check.code.startswith("configured_")
                    or check.code in {
                        "reconciled", "fresh_state", "fresh_prices",
                        "experimental_attribution", "known_fees", "experimental_loss_control",
                    }
                )
            )
    if item.technical_eligibility == "UNKNOWN":
        missing.append("technical_eligibility_not_evaluated")
    reasons = tuple(sorted(set(failed + missing)))
    decision = "REJECT" if failed else "REVIEW_REQUIRED"
    if not failed and not missing and evaluation and evaluation.allowed:
        # Human approval is mandatory, even when all deterministic controls pass.
        decision = "REVIEW_REQUIRED"
    policy_digest = digest(item.policy) if item.policy else None
    return DiagnosticResult(
        decision=decision,
        reason_codes=reasons or ("human_approval_required",),
        failed_controls=tuple(sorted(set(failed))),
        missing_evidence=tuple(sorted(set(missing))),
        policy_version=item.policy.version if item.policy else None,
        policy_digest=policy_digest,
        input_snapshot_digest=snapshot_digest,
        audit_id=digest(("risk-diagnostic-v09", snapshot_digest)),
        evaluated_at=now,
        pre_proposal_exposure=before,
        post_proposal_exposure=evaluation.projected_exposure if evaluation else None,
        pre_concentration=before_concentration,
        post_concentration=evaluation.projected_concentration if evaluation else None,
        cash_before_reservations=cash,
        cash_after_reservations_and_proposal=cash_after,
        proposed_capital_scenario=item.proposed_capital_scenario,
        technical_eligibility=item.technical_eligibility,
    )
