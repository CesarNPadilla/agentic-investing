import json
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from types import SimpleNamespace

import pytest

from risk.paper_state import PaperState, PaperStateError
from security.paper_observer_recovery import apply_readonly_recovery, digest
from tests.test_paper_recovery_review import setup, signed_assertion
from workers.paper_event_observer import PaperEventObserver


def fixture(tmp_path):
    store = PaperState.initialize(tmp_path / "state.sqlite", account_binding="a" * 64)
    with store.transaction() as state:
        state["fill_ledger"] = {"trade_cash": "1000", "positions": {}}
        state["paper_event_checks"] = {
            "failed": {"completed": False, "blockers": ["QUOTE_READ_FAILED"]}
        }
    app, path, proposal, key, credential = setup(tmp_path)
    failed = store.read()["paper_event_checks"]
    proposal = proposal.model_copy(update={"failed_journal_sha256": digest(failed)})
    path.write_text(proposal.model_dump_json(), encoding="utf-8")
    options = app.post(
        "/begin/review", headers={"X-Owner-Review-Sha256": proposal.digest()}
    ).json()["publicKey"]
    assert (
        app.post("/complete/review", json=signed_assertion(options, key, credential)).status_code
        == 200
    )
    receipt = json.loads(
        next((tmp_path / "owner-passkey-verifications").glob("*.json")).read_text(encoding="utf-8")
    )
    now = datetime.now(UTC)
    account = SimpleNamespace(
        bracket_stable=True,
        account_unblocked=True,
        empty_inventory=True,
        positions_count=0,
        open_orders_count=0,
        position_quantities=(),
        cash=Decimal(1000),
        equity=Decimal(1000),
        started_at=now,
        received_at=now,
        account_binding_sha256="a" * 64,
        payload_sha256="d" * 64,
    )
    return store, receipt, credential, account


def test_signed_ack_preserves_failed_evidence_and_every_risk_latch(tmp_path):
    store, receipt, credential, account = fixture(tmp_path)
    before = store.read()
    with pytest.raises(PaperStateError):
        PaperEventObserver(store, lambda: None, account_binding="a" * 64)
    result = apply_readonly_recovery(store, receipt, credential, account)
    after = store.read()
    assert after["paper_event_checks"] == before["paper_event_checks"]
    assert after["latch_reasons"] == before["latch_reasons"]
    assert after["latched"] and not after["execution_available"]
    assert not result["risk_latches_cleared"]
    PaperEventObserver(
        store, lambda: None, account_binding="a" * 64, recovery_credential=credential, symbol="SCHB"
    )
    with pytest.raises(PaperStateError):
        apply_readonly_recovery(store, receipt, credential, account)
    with store.transaction() as state:
        state["paper_event_checks"]["new-failure"] = {"completed": False}
    with pytest.raises(PaperStateError):
        PaperEventObserver(
            store,
            lambda: None,
            account_binding="a" * 64,
            recovery_credential=credential,
            symbol="SCHB",
        )


@pytest.mark.parametrize(
    "field,value",
    [
        ("cash", Decimal(999)),
        ("open_orders_count", 1),
        ("bracket_stable", False),
        ("account_binding_sha256", "c" * 64),
    ],
)
def test_nonmatching_or_unsafe_account_cannot_acknowledge(tmp_path, field, value):
    store, receipt, credential, account = fixture(tmp_path)
    setattr(account, field, value)
    with pytest.raises((ValueError, PaperStateError)):
        apply_readonly_recovery(store, receipt, credential, account)
    assert "paper_readonly_recoveries" not in store.read()


def test_stale_snapshot_and_changed_original_failure_block(tmp_path):
    store, receipt, credential, account = fixture(tmp_path)
    with pytest.raises((ValueError, PaperStateError)):
        apply_readonly_recovery(
            store, receipt, credential, account, now=account.started_at + timedelta(seconds=61)
        )
    with store.transaction() as state:
        state["paper_event_checks"]["failed"]["blockers"] = ["DIFFERENT_FAILURE"]
    with pytest.raises((ValueError, PaperStateError)):
        apply_readonly_recovery(store, receipt, credential, account)


def test_deadline_failure_cannot_be_acknowledged_under_quote_recovery_scope(tmp_path):
    store, receipt, credential, account = fixture(tmp_path)
    store.latch("OBSERVER_DEADLINE_MISSED")
    with pytest.raises(PaperStateError):
        apply_readonly_recovery(store, receipt, credential, account)
    assert "paper_readonly_recoveries" not in store.read()
