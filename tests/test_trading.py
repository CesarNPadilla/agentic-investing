from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError
from sqlalchemy.orm import Session

from api.config import Settings
from api.main import create_app
from database.repository import SQLReportRepository
from trading.automation import qualify_strategy
from trading.models import AutomationPolicyInput
from trading.service import ProposalRow, TradingService

AGENT = {"Authorization": "Bearer " + "a" * 32}
HUMAN = {"Authorization": "Bearer " + "h" * 32}


@pytest.fixture
def settings(tmp_path):
    return Settings(
        _env_file=None,
        database_url=f"sqlite:///{tmp_path / 'trading.db'}",
        trading_enabled=True,
        trading_agent_token="a" * 32,
        trading_approval_token="h" * 32,
    )


@pytest.fixture
def client(settings):
    with TestClient(create_app(settings)) as client:
        client.put("/trading/kill-switch", headers=HUMAN, json={"enabled": False})
        yield client


def propose(client, **overrides):
    return client.post(
        "/trading/proposals",
        headers=AGENT,
        json={
            "symbol": "AAPL",
            "side": "buy",
            "quantity": "2",
            "limit_price": "100",
            "strategy": "manual-v1",
            "rationale": "Synthetic workflow test",
            "request_id": str(uuid4()),
            **overrides,
        },
    )


def approve(client, proposal):
    return client.post(
        f"/trading/proposals/{proposal['id']}/approve",
        headers=HUMAN,
        json={"digest": proposal["digest"]},
    )


def execute(client, proposal):
    return client.post(f"/trading/proposals/{proposal['id']}/execute", headers=AGENT)


def test_approval_boundary_and_immutable_details(client):
    p = propose(client).json()
    assert p["status"] == "pending_approval"
    assert execute(client, p).status_code == 409
    route = f"/trading/proposals/{p['id']}/approve"
    assert client.post(route, headers=AGENT, json={"digest": p["digest"]}).status_code == 401
    assert client.post(route, json={"digest": p["digest"]}).status_code == 401
    assert client.post(route, headers=HUMAN, json={"digest": "0" * 64}).status_code == 409
    assert (
        client.post(
            route, headers=HUMAN, json={"digest": p["digest"], "quantity": "999"}
        ).status_code
        == 422
    )
    assert approve(client, p).json()["status"] == "approved"
    assert execute(client, p).json()["status"] == "filled"
    assert execute(client, p).json()["broker_order"]["client_order_id"] == p["id"]
    account = client.get("/trading/account", headers=AGENT).json()
    assert account["cash"] == "9800"
    assert account["positions"] == {"AAPL": "2"}
    events = client.get("/trading/audit", headers=HUMAN).json()
    assert [e["event"] for e in events] == ["kill_switch", "proposed", "approved", "filled"]


def test_idempotency_and_risk(client):
    p = propose(client, request_id="stable").json()
    assert propose(client, request_id="stable").json() == p
    assert propose(client, request_id="stable", quantity="3").status_code == 409
    for values in ({"quantity": "11"}, {"symbol": "GME"}, {"side": "sell"}):
        p = propose(client, **values).json()
        assert p["status"] == "blocked"
        assert approve(client, p).status_code == 409
    for values in (
        {"quantity": "NaN"},
        {"limit_price": "-1"},
        {"order_type": "market"},
        {"account_id": "live"},
        {"quantity": "0"},
    ):
        assert propose(client, **values).status_code == 422


def test_kill_switch_rechecks_after_approval(client):
    p = propose(client).json()
    approve(client, p)
    assert (
        client.put("/trading/kill-switch", headers=AGENT, json={"enabled": True}).status_code == 401
    )
    client.put("/trading/kill-switch", headers=HUMAN, json={"enabled": True})
    assert execute(client, p).json()["status"] == "blocked"
    assert client.get("/trading/account", headers=AGENT).json()["cash"] == "10000"


def test_restart_and_concurrent_execution(settings, client):
    p = propose(client).json()
    approve(client, p)
    with TestClient(create_app(settings)) as second:
        with ThreadPoolExecutor(max_workers=4) as pool:
            results = list(pool.map(lambda _: execute(second, p), range(8)))
        assert all(r.status_code == 200 and r.json()["status"] == "filled" for r in results)
        assert second.get("/trading/account", headers=AGENT).json()["cash"] == "9800"
        assert second.get(f"/trading/proposals/{p['id']}", headers=HUMAN).json()["approval"]


def test_changed_exposure_blocks_later_execution(client):
    proposals = [propose(client, quantity="10").json() for _ in range(3)]
    for p in proposals:
        assert approve(client, p).json()["status"] == "approved"
    assert execute(client, proposals[0]).json()["status"] == "filled"
    assert execute(client, proposals[1]).json()["status"] == "filled"
    assert execute(client, proposals[2]).json()["status"] == "blocked"


def test_rejection_and_expiry(client, settings):
    p = propose(client).json()
    assert (
        client.post(f"/trading/proposals/{p['id']}/reject", headers=HUMAN).json()["status"]
        == "rejected"
    )
    assert approve(client, p).status_code == 409
    p = propose(client).json()
    repository = SQLReportRepository(settings.database_url)
    with Session(repository.engine) as session, session.begin():
        row = session.get(ProposalRow, p["id"])
        row.payload = {
            **row.payload,
            "expires_at": (datetime.now(UTC) - timedelta(seconds=1)).isoformat(),
        }
    assert approve(client, p).json()["status"] == "expired"
    repository.close()


def test_safe_defaults_and_credentials(settings):
    for values in ({}, {"trading_agent_token": "a" * 32, "trading_approval_token": "a" * 32}):
        with pytest.raises(ValidationError):
            Settings(_env_file=None, trading_enabled=True, **values)
    with TestClient(create_app(settings)) as client:
        assert propose(client).json()["status"] == "blocked"
        assert client.get("/health").json()["live_trading_enabled"] is False
        assert client.get("/trading/account").status_code == 401


def test_audit_failure_rolls_back_fill(client, settings, monkeypatch):
    p = propose(client).json()
    approve(client, p)
    from sqlalchemy.exc import SQLAlchemyError

    def fail(*args, **kwargs):
        raise SQLAlchemyError("private error")

    monkeypatch.setattr(TradingService, "_audit", fail)
    assert execute(client, p).status_code == 503
    assert client.get("/trading/account", headers=AGENT).json()["cash"] == "10000"
    assert client.get(f"/trading/proposals/{p['id']}", headers=AGENT).json()["status"] == "approved"


def test_reconcile_and_sell(client, settings):
    p = propose(client).json()
    approve(client, p)
    execute(client, p)
    sale = propose(client, side="sell", quantity="1", limit_price="110").json()
    approve(client, sale)
    execute(client, sale)
    result = client.post("/trading/reconcile", headers=HUMAN).json()
    assert result["matched"] and result["fills_checked"] == 2
    assert client.get("/trading/account", headers=AGENT).json()["cash"] == "9910"
    from trading.service import ControlRow

    repository = SQLReportRepository(settings.database_url)
    with Session(repository.engine) as session, session.begin():
        row = session.get(ControlRow, 1)
        row.payload = {**row.payload, "cash": "1"}
    assert not client.post("/trading/reconcile", headers=HUMAN).json()["matched"]
    assert client.get("/trading/account", headers=AGENT).json()["killed"] is True
    repository.close()


def test_automation_qualification_requires_predeclared_forward_evidence():
    from datetime import UTC, datetime, timedelta
    from types import SimpleNamespace

    policy = AutomationPolicyInput(strategy="sma")
    registered = datetime(2024, 1, 1, tzinfo=UTC)

    def run(mode, created_at, start, count, revision, metrics):
        bars = [SimpleNamespace(timestamp=start + timedelta(days=index)) for index in range(count)]
        history = SimpleNamespace(
            symbol="AAPL", is_sample=False, adjustment="all", bars=bars
        )
        benchmark = SimpleNamespace(is_sample=False, adjustment="all")
        inputs = SimpleNamespace(
            strategy=SimpleNamespace(name="sma", version="1", fast=20, slow=50),
            history=history,
            benchmark=benchmark,
        )
        return SimpleNamespace(
            mode=mode, created_at=created_at, inputs=inputs, revision=revision, metrics=metrics
        )

    backtest = run(
        "backtest",
        datetime(2024, 1, 2, tzinfo=UTC),
        datetime(2023, 1, 1, tzinfo=UTC),
        100,
        0,
        {"excess_return": "0.06", "max_drawdown": "-0.12", "sharpe_ratio": 1.1},
    )
    paper_start = max(
        backtest.inputs.history.bars[-1].timestamp + timedelta(days=1),
        registered + timedelta(days=1),
    )
    paper = run(
        "paper",
        datetime(2024, 5, 1, tzinfo=UTC),
        paper_start,
        60,
        59,
        {"total_return": "0.01", "max_drawdown": "-0.08"},
    )
    assert qualify_strategy(policy, registered, backtest, paper) == {"passed": True, "reasons": []}

    paper.inputs.strategy.fast = 10
    result = qualify_strategy(policy, registered, backtest, paper)
    assert not result["passed"]
    assert "Paper SMA windows do not match policy" in result["reasons"]
    paper.inputs.strategy.fast = 20

    backtest.metrics["sharpe_ratio"] = 0.79
    result = qualify_strategy(policy, registered, backtest, paper)
    assert not result["passed"]
    assert "Backtest sharpe_ratio must be at least 0.8" in result["reasons"]

    paper.inputs.history.bars[0] = SimpleNamespace(timestamp=registered - timedelta(days=1))
    result = qualify_strategy(policy, registered, backtest, paper)
    assert not result["passed"]
    assert "Paper observations must begin after policy registration" in result["reasons"]


def test_automation_policy_is_audited_and_execution_stays_disabled(client):
    response = client.put(
        "/trading/automation/policy",
        headers=HUMAN,
        json={"strategy": "sma"},
    )
    assert response.status_code == 200
    status = response.json()
    assert status["execution_enabled"] is False
    assert status["execution_available"] is False
    assert status["qualified"] is False
    assert status["policy"]["policy"]["max_daily_loss"] == "100"
    assert status["policy"]["policy"]["trading_session"] == "us_regular"
    assert status["policy"]["policy"]["allowed_order_type"] == "limit"
    assert client.post("/trading/automation/orders", headers=AGENT).status_code == 404
    events = client.get("/trading/audit", headers=HUMAN).json()
    assert events[-1]["event"] == "automation_policy_registered"


def test_automation_policy_requires_human_and_bounded_limits(client):
    assert (
        client.put("/trading/automation/policy", headers=AGENT, json={"strategy": "sma"})
        .status_code
        == 401
    )
    assert (
        client.put(
            "/trading/automation/policy",
            headers=HUMAN,
            json={"strategy": "sma", "max_daily_loss": "101"},
        ).status_code
        == 422
    )
    assert (
        client.put(
            "/trading/automation/policy",
            headers=HUMAN,
            json={"strategy": "sma", "max_portfolio_exposure": "NaN"},
        ).status_code
        == 422
    )


def test_automation_qualification_rejects_replayed_paper_run_and_audits(client):
    assert (
        client.put("/trading/automation/policy", headers=HUMAN, json={"strategy": "sma"})
        .status_code
        == 200
    )
    history = {
        "symbol": "AAPL",
        "source": "historical-fixture",
        "adjustment": "all",
        "is_sample": True,
        "bars": [{"timestamp": "2020-01-02T21:00:00Z", "close": "100"}],
    }
    request = {
        "strategy": {"name": "sma"},
        "history": history,
        "benchmark": {**history, "symbol": "SPY"},
        "initial_cash": "10000",
    }
    backtest = client.post("/backtests", json=request).json()
    paper = client.post("/paper-sessions", json=request).json()
    result = client.post(
        "/trading/automation/qualification",
        headers=HUMAN,
        json={"backtest_id": backtest["id"], "paper_run_id": paper["id"]},
    )
    assert result.status_code == 200
    status = result.json()
    assert not status["qualified"]
    assert status["execution_available"] is False
    reasons = status["policy"]["qualification"]["reasons"]
    assert "Paper evidence cannot use sample data" in reasons
    assert "Paper observations must begin after policy registration" in reasons
    events = client.get("/trading/audit", headers=HUMAN).json()
    assert events[-1]["event"] == "automation_rejected"
