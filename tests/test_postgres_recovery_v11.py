"""Crash qualification is permitted only in the runner's disposable container."""
import os
import re
import subprocess
import time
from decimal import Decimal
from uuid import uuid4

import psycopg
import pytest
from psycopg import sql
from psycopg.conninfo import conninfo_to_dict

from risk.postgres_synthetic_v11 import PostgresSyntheticError, PostgresSyntheticScope
from tests.test_loss_accounting_v11 import NOW
from tests.test_loss_accounting_v11 import evidence as loss_evidence
from tests.test_sleeve_v11 import evidence

DSN = os.environ.get("AIL_V11D_SYNTHETIC_TEST_DSN")
CONTAINER = os.environ.get("AIL_V11G_DISPOSABLE_CONTAINER_ID")
pytestmark = pytest.mark.skipif(not DSN or not CONTAINER,
    reason="Explicit disposable recovery qualification environment required")


def assert_disposable():
    assert re.fullmatch(r"[0-9a-f]{64}", CONTAINER)
    info = subprocess.check_output(["docker", "inspect", "--format",
        '{{.Name}} {{index .Config.Labels "agentic.synthetic-qualification"}}', CONTAINER], text=True).strip()
    assert re.fullmatch(r"/agentic-v11d-test-[0-9a-f]{12} v11g", info)
    connection = conninfo_to_dict(DSN)
    assert connection["host"] == "127.0.0.1" and connection["dbname"] == "synthetic_v11d"


def command(action):
    assert_disposable()
    subprocess.run(["docker", action, CONTAINER], check=True, capture_output=True)


def ready():
    for _ in range(30):
        try:
            with psycopg.connect(DSN) as db:
                db.execute("SELECT 1")
            return
        except psycopg.Error:
            time.sleep(1)
    pytest.fail("Disposable PostgreSQL failed to recover")


def scope():
    s = PostgresSyntheticScope(DSN, "synthetic_v11d_"+uuid4().hex)
    s.initialize(cash=Decimal(1000), sleeve=Decimal(750), initial_latched=False)
    return s


@pytest.fixture(scope="module")
def recovered():
    assert_disposable()
    healthy, loss, partial, uncommitted = scope(), scope(), scope(), scope()
    healthy.assess_and_reserve("ack-lost", "AAPL", evidence())
    loss.record_loss_accounting(loss_evidence(), now=NOW)
    partial.assess_and_reserve("partial", "AAPL", evidence())
    partial.reconcile("partial", cumulative_filled=Decimal(100), status="PARTIAL")
    db = psycopg.connect(DSN)
    try:
        db.execute(sql.SQL("UPDATE {} SET state=jsonb_set(state, '{{latched}}', 'true')").format(uncommitted._table))
        # No commit: abruptly kill only the labeled disposable test database.
        command("kill")
        command("start")
        ready()
    finally:
        db.close()
    return healthy, loss, partial, uncommitted


def test_crash_and_lost_ack_retry_do_not_duplicate_reservation(recovered):
    s = recovered[0]
    result = PostgresSyntheticScope(DSN, s.schema_name).assess_and_reserve("ack-lost", "AAPL", evidence())
    assert result.reservation_present and result.committed == 250 and not result.execution_available
    assert s.snapshot()["order_count"] == 1


def test_committed_baseline_and_loss_latch_survive_database_process_crash(recovered):
    s = recovered[1]
    assert s.snapshot()["latched"]
    result = s.assess_and_reserve("after-crash", "AAPL", evidence())
    assert not result.reservation_present and "KILL_SWITCH" in result.diagnostic.reason_codes
    with psycopg.connect(DSN) as db:
        state = db.execute(sql.SQL("SELECT state FROM {}").format(s._table)).fetchone()[0]
        assert state["loss_accounting"]["evidence"] == loss_evidence().model_dump_json()


def test_partial_fill_unknown_status_hold_and_verified_release_after_crash(recovered):
    s = recovered[2]
    assert s.snapshot()["committed"] == "250"
    assert s.reconcile("partial", cumulative_filled=Decimal(100), status="UNKNOWN")["committed"] == "250"
    assert s.reconcile("partial", cumulative_filled=Decimal(100), status="CANCELED",
                       synthetic_terminal_verified=True)["committed"] == "100"


def test_uncommitted_state_change_is_rolled_back_after_crash(recovered):
    s = recovered[3]
    assert not s.snapshot()["latched"]
    assert s.snapshot()["order_count"] == 0


def test_database_outage_cannot_return_success_or_create_reservation(recovered):
    s = scope()
    command("stop")
    try:
        with pytest.raises(PostgresSyntheticError):
            s.assess_and_reserve("outage", "AAPL", evidence())
    finally:
        command("start")
        ready()
    assert s.snapshot()["order_count"] == 0


@pytest.mark.parametrize("mutation", ["not-a-number", "NaN", "-1"])
def test_malformed_persisted_numeric_state_blocks_with_typed_error(recovered, mutation):
    s = scope()
    with psycopg.connect(DSN) as db:
        db.execute(sql.SQL("UPDATE {} SET state=jsonb_set(state, '{{cash}}', to_jsonb(%s::text))").format(s._table), (mutation,))
    with pytest.raises(PostgresSyntheticError):
        s.assess_and_reserve("invalid", "AAPL", evidence())
