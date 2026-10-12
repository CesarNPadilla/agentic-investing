from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest
from pydantic import ValidationError

from risk.account_v11 import SyntheticAccountInput, evaluate_synthetic_account
from risk.loss_accounting_v11 import ExternalFlow

NOW = datetime(2026, 10, 2, 15, tzinfo=UTC)
START = NOW.replace(hour=4)


def evidence(**changes):
    return SyntheticAccountInput(**({"day_baseline_at": START, "start_of_day_total_equity": "1000",
        "as_of": NOW, "current_total_equity": "1000", "gross_marked_positions": "800",
        "gross_pending_buys": "100", "security_marked_position": "0", "security_pending_buys": "0",
        "quantity": 1, "conservative_price": "100", "unreserved_settled_cash": "100",
        "all_holdings_and_orders_complete": True, "ledger_marks_and_fees_reconciled": True,
        "day_boundary_verified": True, "kill_switch_latched": False} | changes))


def check(**changes):
    return evaluate_synthetic_account(evidence(**changes), now=NOW)


def test_exact_exposure_boundaries_and_no_permission():
    result = check()
    assert result.account_checks_passed and result.projected_gross_exposure == 1000
    assert result.projected_security_exposure == 100
    assert not result.execution_available and not result.production_trusted and not result.automatic_liquidation


def test_drawdown_tightens_exposures_but_daily_loss_limit_stays_fixed():
    result = check(current_total_equity="990")
    assert result.daily_loss_limit == 10
    assert result.gross_exposure_limit == 990 and result.security_exposure_limit == 99
    assert {"ACCOUNT_DAILY_LOSS", "ACCOUNT_GROSS_EXPOSURE", "ACCOUNT_SECURITY_CONCENTRATION"} <= set(result.reason_codes)


@pytest.mark.parametrize("flow", ["500", "-200"])
def test_flows_removed_from_loss_but_current_equity_drives_exposure(flow):
    value = Decimal(flow)
    result = check(current_total_equity=Decimal(1000)+value,
        external_flows=(ExternalFlow(flow_id="f", posted_at=NOW, amount=value),))
    assert result.daily_net_pnl == 0 and result.daily_loss_limit == 10
    assert result.gross_exposure_limit == Decimal(1000)+value


@pytest.mark.parametrize("changes,reason", [
    ({"gross_pending_buys": "101"}, "ACCOUNT_GROSS_EXPOSURE"),
    ({"security_pending_buys": "1"}, "ACCOUNT_SECURITY_CONCENTRATION"),
    ({"current_total_equity": "0"}, "ACCOUNT_NONPOSITIVE_EQUITY"),
    ({"unreserved_settled_cash": "99"}, "ACCOUNT_SETTLED_CASH"),
    ({"estimated_fees": "1"}, "ACCOUNT_SETTLED_CASH"),
    ({"all_holdings_and_orders_complete": False}, "ACCOUNT_EVIDENCE_INCOMPLETE"),
    ({"ledger_marks_and_fees_reconciled": False}, "ACCOUNT_EVIDENCE_INCOMPLETE"),
    ({"day_boundary_verified": False}, "ACCOUNT_DAY_BOUNDARY_UNVERIFIED"),
    ({"kill_switch_latched": True}, "KILL_SWITCH"),
    ({"security_marked_position": "101"}, "EXISTING_SECURITY_BREACH_BLOCK_NEW_BUY"),
])
def test_independent_blockers(changes, reason):
    assert reason in check(**changes).reason_codes


@pytest.mark.parametrize("offset", [-1, 61])
def test_stale_or_future_snapshot(offset):
    assert "ACCOUNT_SNAPSHOT_TIME" in evaluate_synthetic_account(evidence(), now=NOW+timedelta(seconds=offset)).reason_codes


def test_loss_just_inside_threshold_and_exact_freshness():
    assert not check(current_total_equity="990.01").daily_loss_breach
    assert evaluate_synthetic_account(evidence(), now=NOW+timedelta(seconds=60)).account_checks_passed


@pytest.mark.parametrize("changes", [{"current_total_equity": "NaN"}, {"quantity": 1.5},
    {"security_pending_buys": "101"}, {"day_baseline_at": NOW+timedelta(seconds=1)},
    {"external_flows": (ExternalFlow(flow_id="f", posted_at=START, amount="1"),)},
    {"evidence_class": "LIVE"}])
def test_invalid_inputs(changes):
    with pytest.raises(ValidationError):
        evidence(**changes)


@pytest.mark.parametrize("month,day", [(3, 8), (11, 1)])
def test_new_york_dst_days_use_local_midnight(month, day):
    from zoneinfo import ZoneInfo
    zone = ZoneInfo("America/New_York")
    start = datetime(2026, month, day, 0, tzinfo=zone)
    cutoff = datetime(2026, month, day, 12, tzinfo=zone)
    data = evidence(day_baseline_at=start, as_of=cutoff)
    assert evaluate_synthetic_account(data, now=cutoff).account_checks_passed


@pytest.mark.parametrize("start", [START+timedelta(hours=1), START-timedelta(days=1)])
def test_wrong_calendar_baseline_rejected(start):
    with pytest.raises(ValidationError):
        evidence(day_baseline_at=start)


def test_existing_breach_requires_review_without_liquidation():
    result = check(security_marked_position="101")
    assert result.existing_security_breach and result.human_review_required
    assert not result.account_checks_passed and not result.automatic_liquidation
