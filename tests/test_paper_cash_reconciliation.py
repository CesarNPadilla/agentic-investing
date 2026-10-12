from datetime import timedelta

import pytest

from portfolio.paper_cash_reconciliation import cash_activity, reconcile_cash
from tests.test_paper_control_pipeline import NOW, reader


def ledger(rows=()):
    return {
        "baseline_at": (NOW - timedelta(days=2)).isoformat(),
        "acquisition_cutoff": NOW.isoformat(),
        "trade_cash": "1000",
        "positions": {},
        "activities": {str(i): {"row": r} for i, r in enumerate(rows)},
    }


def observation(cash=1000):
    return reader().observe().model_copy(update={"cash": cash})


def test_fee_deposit_withdrawal_cash_and_pnl_scope_separate():
    rows = [
        {"activity_type": k, "net_amount": v, "date": (NOW - timedelta(days=1)).isoformat()}
        for k, v in [("FEE", "-1"), ("CSD", "100"), ("CSW", "-20")]
    ]
    report = reconcile_cash(ledger(rows), observation(1079), now=NOW)
    assert (
        report["cash_matches"]
        and report["fee_total"] == "1"
        and report["external_flow_total"] == "80"
    )
    assert not report["settlement_verified"] and not report["execution_available"]


@pytest.mark.parametrize("kind,value", [("FEE", "1"), ("CSD", "-1"), ("CSW", "1"), ("FEE", "NaN")])
def test_contradictory_or_nonfinite_effect_rejected(kind, value):
    with pytest.raises(ValueError):
        cash_activity(
            {"activity_type": kind, "net_amount": value, "date": NOW.isoformat()},
            baseline=NOW - timedelta(days=2),
            cutoff=NOW,
        )


def test_date_only_bootstrap_or_cutoff_day_is_not_invented_timestamp():
    row = {"activity_type": "CSD", "net_amount": "100", "date": NOW.date().isoformat()}
    assert (
        cash_activity(row, baseline=NOW, cutoff=NOW + timedelta(days=1))[1]
        == "CASH_ACTIVITY_BASELINE_DAY_AMBIGUOUS"
    )
    assert (
        cash_activity(row, baseline=NOW - timedelta(days=1), cutoff=NOW)[1]
        == "CASH_ACTIVITY_CUTOFF_DAY_AMBIGUOUS"
    )


def test_unknown_activity_cash_mismatch_and_nonempty_inventory_block():
    report = reconcile_cash(
        ledger([{"activity_type": "UNSUPPORTED_ACTIVITY"}]),
        observation(999).model_copy(update={"positions_count": 1}),
        now=NOW,
    )
    assert {
        "UNMAPPED_CASH_ACTIVITY",
        "ACCOUNT_CASH_LEDGER_MISMATCH",
        "POSITION_QUANTITY_EVIDENCE_REQUIRED",
    } <= set(report["blockers"])


def test_stale_snapshot_and_acquisition_gap_block():
    report = reconcile_cash(ledger(), observation(), now=NOW + timedelta(seconds=61))
    assert "ACCOUNT_SNAPSHOT_TIME" in report["blockers"]
    x = ledger()
    x["acquisition_cutoff"] = (NOW - timedelta(seconds=1)).isoformat()
    assert "LEDGER_SNAPSHOT_CUTOFF_GAP" in reconcile_cash(x, observation(), now=NOW)["blockers"]


def test_complete_nonempty_quantity_snapshot_matches_and_mismatch_blocks():
    from integrations.brokers.alpaca_paper_read import PaperPosition

    x = ledger()
    x["positions"] = {"INTC": "2"}
    obs = observation().model_copy(
        update={
            "positions_count": 1,
            "position_quantities": (PaperPosition(symbol="INTC", quantity=2, market_value=60),),
        }
    )
    assert reconcile_cash(x, obs, now=NOW)["positions_match"]
    x["positions"] = {"INTC": "3"}
    assert "ACCOUNT_POSITION_LEDGER_MISMATCH" in reconcile_cash(x, obs, now=NOW)["blockers"]
