from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest
from pydantic import ValidationError

from risk.loss_accounting_v11 import ExternalFlow, SyntheticLossEvidence, calculate_synthetic_loss

START = datetime(2026, 10, 1, 4, tzinfo=UTC)
NOW = START+timedelta(hours=11)


def evidence(**changes):
    return SyntheticLossEvidence(**({"baseline_id": "fixture", "baseline_at": START,
        "initial_funded_equity": "1000", "daily_baseline_at": START,
        "daily_baseline_marked_equity": "1000", "as_of": NOW, "current_marked_equity": "980",
        "ledger_complete": True, "marks_reconciled": True, "fees_included_in_equity": True,
        "daily_boundary_verified": True} | changes))


def flow(name, amount, at=NOW):
    return ExternalFlow(flow_id=name, posted_at=at, amount=amount)


def test_loss_boundary_and_net_fee_equity():
    result = calculate_synthetic_loss(evidence(), now=NOW)
    assert result.daily_net_pnl == -20 and result.cumulative_net_pnl == -20
    assert result.daily_loss_limit == 20 and result.persistent_latch_required
    assert not result.execution_available


@pytest.mark.parametrize("amount", ["500", "-200"])
def test_external_flows_do_not_hide_or_create_losses(amount):
    result = calculate_synthetic_loss(evidence(current_marked_equity=Decimal(980)+Decimal(amount),
        flows=(flow("f", amount),)), now=NOW)
    assert result.daily_net_pnl == -20 and result.cumulative_net_pnl == -20
    assert result.persistent_latch_required


def test_next_day_keeps_cumulative_baseline_and_flow_adjusted_denominator():
    next_day = START+timedelta(days=1)
    result = calculate_synthetic_loss(evidence(daily_baseline_at=next_day,
        daily_baseline_marked_equity="1400", as_of=next_day+timedelta(hours=11),
        current_marked_equity="1382", flows=(flow("deposit", "500"),)), now=next_day+timedelta(hours=11))
    assert result.start_of_day_flow_adjusted_equity == 900
    assert result.daily_net_pnl == -18 and result.cumulative_net_pnl == -118
    assert result.daily_loss_limit == 18 and result.cumulative_loss_limit == 100
    assert result.persistent_latch_required


@pytest.mark.parametrize("field", ["ledger_complete", "marks_reconciled", "fees_included_in_equity", "daily_boundary_verified"])
def test_missing_verification_blocks(field):
    result = calculate_synthetic_loss(evidence(**{field: False}), now=NOW)
    assert not result.accounting_available and result.daily_net_pnl is None


@pytest.mark.parametrize("offset", [-1, 61])
def test_future_or_stale_snapshot_blocks(offset):
    assert not calculate_synthetic_loss(evidence(), now=NOW+timedelta(seconds=offset)).accounting_available


def test_exact_snapshot_age_and_nonpositive_equity():
    assert calculate_synthetic_loss(evidence(), now=NOW+timedelta(seconds=60)).accounting_available
    result = calculate_synthetic_loss(evidence(current_marked_equity="-1"), now=NOW)
    assert not result.accounting_available and result.persistent_latch_required


@pytest.mark.parametrize("changes", [
    {"flows": (flow("same", "1"), flow("same", "2"))},
    {"flows": (flow("future", "1", NOW+timedelta(seconds=1)),)},
    {"daily_baseline_at": START-timedelta(seconds=1)},
    {"current_marked_equity": "NaN"}, {"initial_funded_equity": "1001"},
    {"daily_baseline_marked_equity": "999"},
])
def test_invalid_evidence_rejected(changes):
    with pytest.raises(ValidationError):
        evidence(**changes)
