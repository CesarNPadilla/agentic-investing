"""Scoped acknowledgement for an empty-account read-only observer, never risk reset."""

import hashlib
import json
from datetime import UTC, datetime
from decimal import Decimal

from security.paper_recovery_review import RecoveryReview, verify_review_receipt


def digest(value):
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()


def apply_readonly_recovery(store, receipt, credential, observation, *, now=None):
    now = now or datetime.now(UTC)
    if (
        not observation.bracket_stable
        or not observation.account_unblocked
        or not observation.empty_inventory
        or observation.positions_count
        or observation.open_orders_count
        or observation.position_quantities
        or observation.cash != Decimal(1000)
        or observation.equity != Decimal(1000)
        or not observation.started_at <= observation.received_at <= now
        or (now - observation.started_at).total_seconds() > 60
    ):
        raise ValueError("Fresh empty-account reconciliation required")
    proposal = RecoveryReview.model_validate(receipt["review"])
    with store.transaction() as state:
        if {"OBSERVER_DEADLINE_MISSED", "ACTIVE_SCOPE_MONITORING_DEADLINE_MISSED"} & set(
            state["latch_reasons"]
        ):
            raise ValueError("Deadline recovery is outside this scope")
        failed = {
            key: row
            for key, row in state.get("paper_event_checks", {}).items()
            if row.get("completed") is not True
        }
        if (
            state["binding"] != proposal.account_binding_sha256
            or state["binding"] != observation.account_binding_sha256
            or len(failed) != proposal.failed_check_count
        ):
            raise ValueError("Recovery account or journal changed")
        ledger = state.get("fill_ledger", {})
        if ledger.get("positions") or Decimal(ledger.get("trade_cash", "0")) != observation.cash:
            raise ValueError("Empty-account ledger comparison required")
        verify_review_receipt(
            receipt,
            credential,
            expected_review=proposal,
            current_journal_sha256=digest(failed),
            now=now,
        )
        recoveries = state.setdefault("paper_readonly_recoveries", {})
        identifier = proposal.digest()
        if identifier in recoveries:
            raise ValueError("Recovery decision already consumed")
        recoveries[identifier] = {
            "failed_check_ids": sorted(failed),
            "receipt": receipt,
            "applied_at_utc": now.isoformat(),
            "account_read_digest": observation.payload_sha256,
            "account_read_received_at": observation.received_at.isoformat(),
            "purpose": "READ_ONLY_OBSERVER_RESTART_ONLY",
        }
    return {
        "failed_checks_acknowledged": len(failed),
        "failed_checks_preserved": True,
        "risk_latches_cleared": False,
        "execution_available": False,
    }


def acknowledged_failure_ids(state, credential):
    """Reverify historical scoped acknowledgements; never rewrite failure evidence."""
    acknowledged = set()
    for row in state.get("paper_readonly_recoveries", {}).values():
        proposal = RecoveryReview.model_validate(row["receipt"]["review"])
        failed = {key: state["paper_event_checks"][key] for key in row["failed_check_ids"]}
        if (
            proposal.account_binding_sha256 != state["binding"]
            or len(failed) != proposal.failed_check_count
            or any(check.get("completed") is True for check in failed.values())
        ):
            raise ValueError("Acknowledged failed journal changed")
        verify_review_receipt(
            row["receipt"],
            credential,
            expected_review=proposal,
            current_journal_sha256=digest(failed),
            now=datetime.fromisoformat(row["applied_at_utc"]),
        )
        acknowledged.update(failed)
    return acknowledged
