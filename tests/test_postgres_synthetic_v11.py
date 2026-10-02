import os
from concurrent.futures import ThreadPoolExecutor
from decimal import Decimal
from uuid import uuid4

import psycopg
import pytest
from psycopg import sql

from risk.postgres_synthetic_v11 import PostgresSyntheticError, PostgresSyntheticScope
from tests.test_sleeve_v11 import evidence

DSN = os.environ.get("AIL_V11D_SYNTHETIC_TEST_DSN")
pytestmark = pytest.mark.skipif(not DSN, reason="Explicit isolated PostgreSQL test DSN required")


def scope(cash="1000", sleeve="750", latched=False):
    result = PostgresSyntheticScope(DSN, "synthetic_v11d_"+uuid4().hex)
    result.initialize(cash=Decimal(cash), sleeve=Decimal(sleeve), initial_latched=latched)
    return result


def test_atomic_reserve_retry_and_digest_binding():
    s = scope()
    data = evidence()
    result = s.assess_and_reserve("p1", "AAPL", data)
    assert result.reservation_present and result.committed == 250 and not result.execution_available
    assert s.assess_and_reserve("p1", "AAPL", data).committed == 250
    with pytest.raises(PostgresSyntheticError):
        s.assess_and_reserve("p1", "MSFT", data)
    assert s.snapshot()["order_count"] == 1


def test_durable_loss_latch_and_no_reservation():
    s = scope()
    breached = s.assess_and_reserve("loss", "AAPL", evidence(daily_net_pnl="-20"))
    assert breached.latched and not breached.reservation_present
    recovered = PostgresSyntheticScope(DSN, s.schema_name)
    result = recovered.assess_and_reserve("after", "AAPL", evidence())
    assert "KILL_SWITCH" in result.diagnostic.reason_codes
    assert not result.reservation_present and result.latched


def test_same_symbol_and_gross_commitments_enter_risk_check():
    s = scope()
    assert s.assess_and_reserve("first", "AAPL", evidence()).reservation_present
    second = s.assess_and_reserve("second", "AAPL", evidence())
    assert "N03_NAME_CONCENTRATION" in second.diagnostic.reason_codes
    assert not second.reservation_present
    for i, symbol in enumerate(["MSFT", "SPY"]):
        assert s.assess_and_reserve(str(i), symbol, evidence()).reservation_present
    last = s.assess_and_reserve("fourth", "NVDA", evidence())
    assert "N04_AGGREGATE" in last.diagnostic.reason_codes
    assert not last.reservation_present and last.committed == 750


def test_concurrent_proposals_serialized_and_no_oversubscription():
    s = scope(cash="250", sleeve="250")
    with ThreadPoolExecutor(max_workers=4) as pool:
        results = list(pool.map(lambda i: s.assess_and_reserve(str(i), "AAPL", evidence()), range(4)))
    assert sum(r.reservation_present for r in results) == 1
    assert s.snapshot()["committed"] == "250"


def test_concurrent_duplicate_exactly_once():
    s = scope()
    with ThreadPoolExecutor(max_workers=4) as pool:
        results = list(pool.map(lambda _: s.assess_and_reserve("same", "AAPL", evidence()), range(4)))
    assert all(r.reservation_present for r in results)
    assert s.snapshot()["order_count"] == 1 and s.snapshot()["committed"] == "250"


def test_partial_unknown_cancel_restart_preserves_filled_cost():
    s = scope(); s.assess_and_reserve("p", "AAPL", evidence())
    for status in ["PARTIAL", "PENDING_CANCEL", "UNKNOWN", "CANCELED"]:
        result = s.reconcile("p", cumulative_filled=Decimal(100), status=status)
        assert result["committed"] == "250"
    recovered = PostgresSyntheticScope(DSN, s.schema_name)
    result = recovered.reconcile("p", cumulative_filled=Decimal(100), status="CANCELED",
                                 synthetic_terminal_verified=True)
    assert result["committed"] == "100"
    with pytest.raises(PostgresSyntheticError):
        recovered.assess_and_reserve("p", "AAPL", evidence())
    with pytest.raises(PostgresSyntheticError):
        recovered.reconcile("p", cumulative_filled=Decimal(99), status="CANCELED", synthetic_terminal_verified=True)


def test_failed_atomic_update_returns_no_receipt_and_rolls_back():
    s = scope()
    with psycopg.connect(DSN) as db:
        db.execute(sql.SQL("CREATE FUNCTION {}.reject_update() RETURNS trigger LANGUAGE plpgsql AS "
                           "$$ BEGIN RAISE EXCEPTION 'synthetic failure'; END $$").format(s._schema))
        db.execute(sql.SQL("CREATE TRIGGER reject_update BEFORE UPDATE ON {} FOR EACH ROW "
                           "EXECUTE FUNCTION {}.reject_update()").format(s._table, s._schema))
    with pytest.raises(PostgresSyntheticError):
        s.assess_and_reserve("p", "AAPL", evidence(daily_net_pnl="-20"))
    with psycopg.connect(DSN) as db:
        state = db.execute(sql.SQL("SELECT state FROM {}").format(s._table)).fetchone()[0]
        assert not state["latched"] and state["orders"] == {} and state["events"] == []


def test_missing_scope_and_corrupt_state_block():
    with pytest.raises(PostgresSyntheticError):
        PostgresSyntheticScope(DSN, "synthetic_v11d_"+uuid4().hex).snapshot()
    s = scope()
    with psycopg.connect(DSN) as db:
        db.execute(sql.SQL("UPDATE {} SET state='{{}}'::jsonb").format(s._table))
    with pytest.raises(PostgresSyntheticError):
        s.assess_and_reserve("p", "AAPL", evidence())


def test_default_latch_and_existing_scope_refusal():
    s = scope(latched=True)
    assert not s.assess_and_reserve("p", "AAPL", evidence()).reservation_present
    with pytest.raises(PostgresSyntheticError):
        s.initialize(cash=Decimal(1000), sleeve=Decimal(750))


def test_reservation_capacity_is_explicit_rejection():
    s = scope(sleeve="100")
    result = s.assess_and_reserve("p", "AAPL", evidence())
    assert not result.diagnostic.sleeve_checks_passed
    assert "RESERVATION_CAPACITY" in result.diagnostic.reason_codes
    assert not result.reservation_present


def test_real_serialization_failure_retries_fresh_state():
    s = scope()
    attempts = []
    def operation(state):
        attempts.append(state["latched"])
        state["latched"] = True
        if len(attempts) == 1:
            raise psycopg.errors.SerializationFailure("synthetic retry fixture")
        return True
    assert s._transaction(operation)
    assert attempts == [False, False]
    assert s.snapshot()["latched"]


def test_retry_exhaustion_rolls_back_all_attempts():
    s = scope()
    attempts = []
    def operation(state):
        attempts.append(state["latched"])
        state["latched"] = True
        raise psycopg.errors.SerializationFailure("synthetic retry fixture")
    with pytest.raises(PostgresSyntheticError):
        s._transaction(operation)
    assert attempts == [False]*5
    assert not s.snapshot()["latched"]


def test_cumulative_loss_latches_without_reserving():
    s = scope()
    result = s.assess_and_reserve("loss", "AAPL", evidence(cumulative_net_pnl="-100"))
    assert result.latched and not result.reservation_present
    assert "N07_CUMULATIVE_LOSS" in result.diagnostic.reason_codes


def test_concurrent_loss_and_reservation_preserve_final_latch():
    s = scope()
    def assess(i):
        return s.assess_and_reserve(str(i), "AAPL", evidence(daily_net_pnl="-20") if i == 0 else evidence())
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(assess, range(2)))
    assert s.snapshot()["latched"]
    assert sum(result.reservation_present for result in results) <= 1
    assert not s.assess_and_reserve("after", "MSFT", evidence()).reservation_present


def test_bound_evidence_is_checked_inside_atomic_reservation():
    import hashlib

    from risk.evidence_v11 import SyntheticReviewBinding
    from tests.test_evidence_v11 import bundle
    s = scope(); data = evidence(); b = bundle()
    digest = hashlib.sha256(("AAPL\n"+data.model_dump_json()).encode()).hexdigest()
    binding = SyntheticReviewBinding(evidence_digest=b.digest(), proposal_digest=digest,
                                      risk_evaluated_at=data.risk_evaluation_time)
    assert s.assess_and_reserve("bound", "AAPL", data, evidence_bundle=b, review=binding).reservation_present


@pytest.mark.parametrize("change", ["stale", "changed", "missing", "mismatch"])
def test_invalid_bound_evidence_cannot_reserve(change):
    import hashlib
    from datetime import timedelta

    from risk.evidence_v11 import SyntheticReviewBinding
    from tests.test_evidence_v11 import bundle
    s = scope(); data = evidence(); original = bundle()
    digest = hashlib.sha256(("AAPL\n"+data.model_dump_json()).encode()).hexdigest()
    binding = SyntheticReviewBinding(evidence_digest=original.digest(), proposal_digest=digest,
                                      risk_evaluated_at=data.risk_evaluation_time)
    b = original
    if change == "stale":
        b = bundle(quote_event_time=data.now-timedelta(seconds=31))
    elif change == "changed":
        b = bundle(policy_digest="d"*64)
    elif change == "missing":
        binding = None
    else:
        b = bundle(ask="251")
    result = s.assess_and_reserve("blocked", "AAPL", data, evidence_bundle=b, review=binding)
    assert not result.reservation_present and not result.diagnostic.sleeve_checks_passed
    assert s.snapshot()["order_count"] == 0
