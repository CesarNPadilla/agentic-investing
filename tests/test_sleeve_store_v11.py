import sqlite3
from concurrent.futures import ThreadPoolExecutor

import pytest

from risk.sleeve_store_v11 import SyntheticSleeveStore, SyntheticStoreError
from tests.test_sleeve_v11 import evidence


def test_default_initialization_is_latched_and_restart_cannot_clear(tmp_path):
    path = tmp_path / "synthetic.db"
    store = SyntheticSleeveStore.initialize(path)
    result = store.evaluate_and_record(evidence(kill_switch_latched=False))
    assert "KILL_SWITCH" in result.reason_codes
    assert SyntheticSleeveStore(path).latched()
    assert not result.execution_available


@pytest.mark.parametrize("pnl", [{"daily_net_pnl": "-20"}, {"cumulative_net_pnl": "-100"}])
def test_loss_latch_survives_recovery_restart_and_caller_input(tmp_path, pnl):
    path = tmp_path / "synthetic.db"
    store = SyntheticSleeveStore.initialize(path, synthetic_initial_latched=False)
    assert store.evaluate_and_record(evidence()).sleeve_checks_passed
    assert store.evaluate_and_record(evidence(**pnl)).persistent_latch_required
    recovered = SyntheticSleeveStore(path).evaluate_and_record(evidence())
    assert "KILL_SWITCH" in recovered.reason_codes and not recovered.sleeve_checks_passed


def test_missing_store_does_not_recreate_state(tmp_path):
    path = tmp_path / "missing.db"
    with pytest.raises(SyntheticStoreError):
        SyntheticSleeveStore(path).evaluate_and_record(evidence())
    assert not path.exists()


def test_cannot_overwrite_or_use_an_existing_database(tmp_path):
    path = tmp_path / "existing.db"
    with sqlite3.connect(path) as db:
        db.execute("CREATE TABLE production_marker (value TEXT)")
    with pytest.raises(SyntheticStoreError):
        SyntheticSleeveStore.initialize(path)
    with pytest.raises(SyntheticStoreError):
        SyntheticSleeveStore(path).latched()


@pytest.mark.parametrize("mutation", [
    "UPDATE journal SET payload='{}' WHERE seq=2",
    "DELETE FROM journal WHERE seq=1",
    "UPDATE journal SET digest='bad' WHERE seq=2",
])
def test_tampered_state_blocks_evaluation(tmp_path, mutation):
    path = tmp_path / "synthetic.db"
    store = SyntheticSleeveStore.initialize(path, synthetic_initial_latched=False)
    store.evaluate_and_record(evidence())
    with sqlite3.connect(path) as db:
        db.execute(mutation)
    with pytest.raises(SyntheticStoreError):
        store.evaluate_and_record(evidence())


def test_concurrent_loss_and_healthy_inputs_leave_durable_latch(tmp_path):
    path = tmp_path / "synthetic.db"
    SyntheticSleeveStore.initialize(path, synthetic_initial_latched=False)
    values = [evidence(), evidence(daily_net_pnl="-20"), evidence(), evidence()]
    with ThreadPoolExecutor(max_workers=4) as pool:
        results = list(pool.map(lambda value: SyntheticSleeveStore(path).evaluate_and_record(value), values))
    assert all(not result.execution_available for result in results)
    assert SyntheticSleeveStore(path).latched()
    with sqlite3.connect(path) as db:
        assert db.execute("SELECT count(*) FROM journal").fetchone()[0] == 5


def test_failed_append_rolls_back_and_returns_no_pass(tmp_path):
    path = tmp_path / "synthetic.db"
    store = SyntheticSleeveStore.initialize(path, synthetic_initial_latched=False)
    with sqlite3.connect(path) as db:
        db.execute("CREATE TRIGGER fail_append BEFORE INSERT ON journal "
                   "BEGIN SELECT RAISE(ABORT, 'fixture failure'); END")
    with pytest.raises(SyntheticStoreError):
        store.evaluate_and_record(evidence())
    with sqlite3.connect(path) as db:
        assert db.execute("SELECT count(*) FROM journal").fetchone()[0] == 1


def test_manual_latch_remains_sticky_and_no_reset_method(tmp_path):
    store = SyntheticSleeveStore.initialize(tmp_path / "synthetic.db", synthetic_initial_latched=False)
    store.evaluate_and_record(evidence(kill_switch_latched=True))
    assert store.latched()
    assert not hasattr(store, "reset")


def test_nonboolean_bootstrap_is_rejected(tmp_path):
    with pytest.raises(SyntheticStoreError):
        SyntheticSleeveStore.initialize(tmp_path / "synthetic.db", synthetic_initial_latched="false")
