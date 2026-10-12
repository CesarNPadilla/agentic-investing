from datetime import UTC, datetime, timedelta

import pytest

from integrations.brokers.alpaca_paper_activities import PaperActivities
from portfolio.paper_daily_flows import retain_daily_activity
from risk.paper_daily_loss import BoundaryEvidence, retain_boundary_evidence
from risk.paper_state import PaperState, PaperStateError

START = datetime(2026, 10, 5, 4, tzinfo=UTC)


def setup(tmp_path):
    store = PaperState.initialize(tmp_path / "paper.sqlite", account_binding="a" * 64)
    retain_boundary_evidence(
        store,
        BoundaryEvidence(
            account_binding="a" * 64,
            source_digest="b" * 64,
            source_description="TEST FIXTURE",
            as_of=START,
            equity=1000,
        ),
    )
    return store


def batch(rows=(), **changes):
    values = {
        "after": START,
        "until": START + timedelta(hours=10),
        "received_at": START + timedelta(hours=10, seconds=1),
        "rows": rows,
        "page_digests": (),
        "pagination_exhausted": True,
    }
    values.update(changes)
    return PaperActivities(**values)


def test_empty_pages_do_not_establish_zero_flows(tmp_path):
    result = retain_daily_activity(setup(tmp_path), batch(), account_binding="a" * 64)
    assert result["observed_external_flow_total"] == "0"
    assert result["external_flow_total_for_risk"] is None


def test_timestamped_flows_and_fees_replay_once_after_restart(tmp_path):
    store = setup(tmp_path)
    rows = [
        {
            "id": "d",
            "activity_type": "CSD",
            "net_amount": "100",
            "date": (START + timedelta(hours=1)).isoformat(),
        },
        {
            "id": "f",
            "activity_type": "FEE",
            "net_amount": "-1",
            "date": (START + timedelta(hours=2)).isoformat(),
        },
    ]
    result = retain_daily_activity(store, batch(rows), account_binding="a" * 64)
    assert result["observed_external_flow_total"] == "100"
    assert result["observed_fee_total"] == "1"
    assert (
        retain_daily_activity(PaperState(store.path), batch(rows), account_binding="a" * 64)
        == result
    )
    rows[0]["net_amount"] = "200"
    with pytest.raises(PaperStateError):
        retain_daily_activity(store, batch(rows), account_binding="a" * 64)
    assert (
        store.read()["paper_daily_activity"]["2026-10-05"]["observed_external_flow_total"] == "100"
    )


def test_date_only_and_unknown_activity_block(tmp_path):
    rows = [
        {"id": "d", "activity_type": "CSD", "net_amount": "100", "date": "2026-10-05"},
        {"id": "x", "activity_type": "UNKNOWN"},
    ]
    result = retain_daily_activity(setup(tmp_path), batch(rows), account_binding="a" * 64)
    assert "CASH_ACTIVITY_BASELINE_DAY_AMBIGUOUS" in result["blockers"]
    assert "UNMAPPED_CASH_ACTIVITY" in result["blockers"]


def test_gap_and_incomplete_pagination_roll_back(tmp_path):
    store = setup(tmp_path)
    for changes in ({"after": START + timedelta(minutes=1)}, {"pagination_exhausted": False}):
        with pytest.raises(PaperStateError):
            retain_daily_activity(store, batch(**changes), account_binding="a" * 64)
    assert "paper_daily_activity" not in store.read()


def test_disappearing_activity_is_retained_and_blocks(tmp_path):
    store = setup(tmp_path)
    row = {
        "id": "d",
        "activity_type": "CSD",
        "net_amount": "100",
        "date": (START + timedelta(hours=1)).isoformat(),
    }
    retain_daily_activity(store, batch([row]), account_binding="a" * 64)
    result = retain_daily_activity(store, batch(), account_binding="a" * 64)
    assert result["activity_count"] == 1
    assert "DAILY_ACTIVITY_MISSING_FROM_FRESH_READ" in result["blockers"]
