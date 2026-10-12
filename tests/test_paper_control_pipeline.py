import sqlite3
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta

import httpx
import pytest

from integrations.brokers.alpaca_paper_read import AlpacaPaperAccountReader
from market_data.base import ProviderUnavailable
from risk.paper_state import PaperState, PaperStateError
from scripts.observe_alpaca_paper import cycle

NOW = datetime(2026, 10, 5, 15, tzinfo=UTC)
BINDING = "a" * 64


def reader(*, changed=False, orders=None, status=200):
    count = 0

    def handler(request):
        nonlocal count
        assert request.method == "GET" and request.url.host == "paper-api.alpaca.markets"
        if request.url.path == "/v2/account":
            count += 1
            value = {
                "id": "private-account",
                "status": "ACTIVE",
                "equity": "100000",
                "cash": "100000",
                "trading_blocked": False,
                "account_blocked": False,
                "trade_suspended_by_user": False,
            }
            if changed and count == 2:
                value["cash"] = "99999"
            return httpx.Response(status, json=value)
        return httpx.Response(200, json=(orders or []) if request.url.path == "/v2/orders" else [])

    return AlpacaPaperAccountReader(
        "key", "secret", transport=httpx.MockTransport(handler), clock=lambda: NOW
    )


def test_bracketed_empty_observation_does_not_certify_settlement():
    observed = reader().observe()
    assert observed.bracket_stable and observed.empty_inventory and observed.account_unblocked
    assert not observed.execution_available and not observed.settled_cash_verified
    assert "TRANSACTION_LEDGER_UNRECONCILED" in observed.reasons(NOW)
    assert "ACCOUNT_SNAPSHOT_TIME" in observed.reasons(NOW + timedelta(seconds=61))
    assert "private-account" not in observed.model_dump_json()


def test_changed_account_blocks():
    observed = reader(changed=True).observe()
    assert "ACCOUNT_CHANGED_DURING_READ" in observed.reasons(NOW)


@pytest.mark.parametrize("status", [302, 401, 403, 429, 500])
def test_failed_account_reads_do_not_fallback(status):
    with pytest.raises(ProviderUnavailable):
        reader(status=status).observe()


def test_potential_order_truncation_blocks():
    with pytest.raises(ProviderUnavailable):
        reader(orders=[{"id": str(i)} for i in range(500)]).observe()


def test_state_survives_restart_and_replay_mismatch(tmp_path):
    path = tmp_path / "paper.sqlite"
    state = PaperState.initialize(path, account_binding=BINDING)
    state.stage_intent("first", "b" * 64, 100)
    state.stage_intent("first", "b" * 64, 100)
    assert len(PaperState(path).read()["reservations"]) == 1
    with pytest.raises(PaperStateError):
        state.stage_intent("first", "c" * 64, 100)
    state.latch("ACCOUNT_DAILY_LOSS")
    assert "ACCOUNT_DAILY_LOSS" in PaperState(path).read()["latch_reasons"]
    assert PaperState(path).read()["latched"]


def test_concurrent_intents_cannot_exceed_budget(tmp_path):
    path = tmp_path / "paper.sqlite"
    PaperState.initialize(path, account_binding=BINDING)

    def attempt(i):
        try:
            PaperState(path).stage_intent(str(i), "b" * 64, 600)
            return True
        except PaperStateError:
            return False

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(attempt, [1, 2]))
    assert sum(results) == 1


def test_missing_corrupt_and_existing_state_block(tmp_path):
    path = tmp_path / "paper.sqlite"
    with pytest.raises(PaperStateError):
        PaperState(path).read()
    assert not path.exists()
    PaperState.initialize(path, account_binding=BINDING)
    with pytest.raises(PaperStateError):
        PaperState.initialize(path, account_binding=BINDING)
    with sqlite3.connect(path) as db:
        db.execute("UPDATE state SET payload='{}'")
    with pytest.raises(PaperStateError):
        PaperState(path).read()


def test_pipeline_failure_is_latched(tmp_path):
    state = PaperState.initialize(tmp_path / "paper.sqlite", account_binding=BINDING)

    class Broken:
        def observe(self):
            raise RuntimeError("secret")

    report = cycle(Broken(), None, None, state, now=lambda: NOW)
    assert report["latched"] and not report["execution_available"]
    assert "secret" not in str(report)
    assert "OBSERVATION_CYCLE_FAILED" in state.read()["latch_reasons"]


def test_real_observation_account_binding_cannot_change(tmp_path):
    state = PaperState.initialize(tmp_path / "paper.sqlite", account_binding=BINDING)
    with pytest.raises(PaperStateError):
        state.record_observation(reader().observe(), [])
    assert state.read()["observations"] == []


def test_combined_cycle_persists_blockers_without_relabeling_real_data(tmp_path):
    from pathlib import Path

    from market_data.alpaca_evidence import PaperQuoteEvidence
    from market_data.nyse_calendar import NysePublishedCalendar

    account = reader()
    observation = account.observe()
    state = PaperState.initialize(
        tmp_path / "paper.sqlite", account_binding=observation.account_binding_sha256
    )

    class Quotes:
        def read(self, symbol):
            return PaperQuoteEvidence(
                symbol=symbol,
                bid=100,
                ask=101,
                event_time=NOW,
                received_time=NOW,
                raw_sha256="a" * 64,
            )

    calendar = NysePublishedCalendar(
        Path(__file__).resolve().parents[1] / "conf/nyse-calendar-2026.json"
    )
    report = cycle(account, Quotes(), calendar, state, now=lambda: NOW)
    assert report["account_observed"] and report["quote_observed"]
    assert "SETTLED_CASH_UNVERIFIED" in report["blockers"]
    assert len(state.read()["observations"]) == 1
    assert not report["execution_available"] and not report["month_trial_started"]
