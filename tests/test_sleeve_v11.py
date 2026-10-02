from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest
from pydantic import ValidationError

from risk.sleeve_v11 import SyntheticSleeveInput, evaluate_synthetic_sleeve

NOW = datetime(2026, 10, 1, 15, tzinfo=UTC)


def evidence(**changes):
    values = {"initial_funded_sleeve": "1000", "current_flow_adjusted_equity": "1000",
                  "start_of_day_flow_adjusted_equity": "1000", "unreserved_settled_cash": "1000",
                  "acquisition_commitments": "0", "same_name_marked_commitments": "0",
                  "gross_marked_commitments": "0", "quantity": 1, "limit_price": "250",
                  "conservative_price": "250", "daily_net_pnl": "0", "cumulative_net_pnl": "0",
                  "now": NOW, "quote_event_time": NOW, "snapshot_cutoff": NOW,
                  "risk_evaluation_time": NOW, "bound_inputs_unchanged": True,
                  "verified_regular_session": True, "kill_switch_latched": False}
    return SyntheticSleeveInput(**(values | changes))


def test_pass_is_replayable_and_cannot_execute():
    a = evaluate_synthetic_sleeve(evidence())
    assert a == evaluate_synthetic_sleeve(evidence())
    assert a.sleeve_checks_passed and not a.execution_available
    assert not a.automatic_liquidation


@pytest.mark.parametrize("changes,code", [
    ({"acquisition_commitments": "751"}, "N01_CAPITAL_CEILING"),
    ({"unreserved_settled_cash": "249"}, "SETTLED_CASH"),
    ({"same_name_marked_commitments": "1", "gross_marked_commitments": "1"}, "N02_POSITION"),
    ({"current_flow_adjusted_equity": "999"}, "N03_NAME_CONCENTRATION"),
    ({"gross_marked_commitments": "501"}, "N04_AGGREGATE"),
    ({"limit_price": "24", "conservative_price": "24"}, "N05_MINIMUM_ORDER"),
    ({"daily_net_pnl": "-20"}, "N06_DAILY_LOSS"),
    ({"cumulative_net_pnl": "-100"}, "N07_CUMULATIVE_LOSS"),
    ({"quote_event_time": NOW - timedelta(seconds=31)}, "N08_QUOTE_AGE"),
    ({"snapshot_cutoff": NOW - timedelta(seconds=61)}, "N09_SNAPSHOT_AGE"),
    ({"risk_evaluation_time": NOW - timedelta(seconds=300)}, "N10_APPROVAL_EXPIRED"),
    ({"bound_inputs_unchanged": False}, "N10_APPROVAL_EXPIRED"),
    ({"verified_regular_session": False}, "SESSION_UNVERIFIED"),
    ({"kill_switch_latched": True}, "KILL_SWITCH"),
])
def test_independent_rejections(changes, code):
    result = evaluate_synthetic_sleeve(evidence(**changes))
    assert code in result.reason_codes and not result.sleeve_checks_passed


def test_equal_sizing_and_freshness_boundaries_pass():
    result = evaluate_synthetic_sleeve(evidence(acquisition_commitments="750",
        gross_marked_commitments="500", quote_event_time=NOW-timedelta(seconds=30),
        snapshot_cutoff=NOW-timedelta(seconds=60), risk_evaluation_time=NOW-timedelta(seconds=299)))
    assert result.sleeve_checks_passed


@pytest.mark.parametrize("field", ["quote_event_time", "snapshot_cutoff", "risk_evaluation_time"])
@pytest.mark.parametrize("value", [None, NOW + timedelta(seconds=1)])
def test_missing_or_future_timestamps_fail(field, value):
    assert not evaluate_synthetic_sleeve(evidence(**{field: value})).sleeve_checks_passed


def test_smaller_equity_loss_limits_latch_at_equality():
    result = evaluate_synthetic_sleeve(evidence(initial_funded_sleeve="500",
        start_of_day_flow_adjusted_equity="500", daily_net_pnl="-10", cumulative_net_pnl="-50"))
    assert result.daily_loss_limit == Decimal(10)
    assert result.cumulative_loss_limit == Decimal(50)
    assert result.persistent_latch_required
    assert {"N06_DAILY_LOSS", "N07_CUMULATIVE_LOSS"} <= set(result.reason_codes)


@pytest.mark.parametrize("changes", [
    {"quantity": 1.5}, {"quantity": True}, {"current_flow_adjusted_equity": "0"},
    {"daily_net_pnl": "NaN"}, {"now": NOW.replace(tzinfo=None)},
    {"evidence_class": "LIVE"}, {"conservative_price": "249"},
    {"same_name_marked_commitments": "1", "gross_marked_commitments": "0"},
])
def test_invalid_evidence_rejected(changes):
    with pytest.raises(ValidationError):
        evidence(**changes)


def test_existing_name_exposure_also_counts_against_position_cash_ceiling():
    result = evaluate_synthetic_sleeve(evidence(limit_price="100", conservative_price="100",
        same_name_marked_commitments="100", gross_marked_commitments="100",
        unreserved_settled_cash="150"))
    assert "N02_POSITION" in result.reason_codes
    assert "SETTLED_CASH" not in result.reason_codes
    assert not result.whole_account_qualified
