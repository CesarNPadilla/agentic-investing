from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta

import pytest

from integrations.brokers.alpaca_paper_activities import PaperActivities
from portfolio.paper_fill_ledger import PaperFillLedger
from risk.paper_state import PaperStateError
from tests.test_paper_control_pipeline import NOW, reader
from tests.test_paper_fill_reconciliation import fill


def setup(tmp_path):
    observation = reader().observe().model_copy(update={"equity": 1000, "cash": 1000})
    ledger = PaperFillLedger.initialize(tmp_path / "ledger.sqlite", observation)
    return ledger, observation.account_binding_sha256


def batch(rows):
    for row in rows:
        if row.get("activity_type") == "FILL":
            row["transaction_time"] = (NOW + timedelta(seconds=1)).isoformat()
    return PaperActivities(
        after=NOW,
        until=NOW + timedelta(seconds=5),
        received_at=NOW + timedelta(seconds=6),
        rows=rows,
        page_digests=(),
        pagination_exhausted=True,
    )


def test_overlap_restart_and_partial_fill_cash_applied_once(tmp_path):
    ledger, binding = setup(tmp_path)
    result = ledger.import_batch(batch([fill(), fill("2", cum="2")]), account_binding=binding)
    assert result["new_activities"] == 2
    restarted = PaperFillLedger(ledger.store.path)
    assert (
        restarted.import_batch(batch([fill(), fill("2", cum="2")]), account_binding=binding)[
            "new_activities"
        ]
        == 0
    )
    assert restarted.read()["trade_cash"] == "940" and restarted.read()["positions"] == {
        "INTC": "2"
    }
    assert restarted.store.read()["latched"]


def test_corrected_identity_rolls_back_entire_batch(tmp_path):
    ledger, binding = setup(tmp_path)
    ledger.import_batch(batch([fill()]), account_binding=binding)
    row = fill()
    row["price"] = "31"
    before = ledger.read()
    with pytest.raises(PaperStateError):
        ledger.import_batch(batch([fill("2", cum="2"), row]), account_binding=binding)
    assert ledger.read() == before


def test_missing_history_wrong_account_and_gap_block(tmp_path):
    ledger, binding = setup(tmp_path)
    with pytest.raises(PaperStateError):
        ledger.import_batch(batch([fill(cum="2")]), account_binding=binding)
    with pytest.raises(PaperStateError):
        ledger.import_batch(batch([]), account_binding="b" * 64)
    gap = batch([]).model_copy(update={"after": NOW + timedelta(seconds=1)})
    with pytest.raises(PaperStateError):
        ledger.import_batch(gap, account_binding=binding)
    assert not ledger.read()["activities"]


def test_concurrent_duplicate_batches_apply_once(tmp_path):
    ledger, binding = setup(tmp_path)

    def apply(_):
        return PaperFillLedger(ledger.store.path).import_batch(
            batch([fill()]), account_binding=binding
        )["new_activities"]

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(apply, [1, 2]))
    assert sorted(results) == [0, 1] and ledger.read()["trade_cash"] == "970"


def test_unmapped_activity_is_retained_without_cash_assumption(tmp_path):
    ledger, binding = setup(tmp_path)
    ledger.import_batch(
        batch([{"id": "fee", "activity_type": "FEE", "net_amount": "-1"}]), account_binding=binding
    )
    assert ledger.read()["trade_cash"] == "1000"
    assert "UNMAPPED_ACCOUNT_ACTIVITY" in ledger.store.read()["latch_reasons"]


def test_nonempty_or_wrong_baseline_cannot_initialize(tmp_path):
    with pytest.raises(PaperStateError):
        PaperFillLedger.initialize(tmp_path / "ledger.sqlite", reader().observe())
