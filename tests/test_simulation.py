from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from api.config import Settings
from api.main import create_app
from simulation.engine import evaluate
from simulation.models import SimulationInput


def inputs(prices, **overrides):
    history = {
        "symbol": "AAPL",
        "source": "test",
        "adjustment": "all",
        "is_sample": True,
        "bars": [
            {
                "timestamp": datetime(2020, 1, 1, 21, tzinfo=UTC) + timedelta(days=i),
                "close": str(price),
            }
            for i, price in enumerate(prices)
        ],
    }
    return SimulationInput.model_validate(
        dict(
            history=history,
            benchmark={**history, "symbol": "SPY"},
            initial_cash="1000",
            strategy={"name": "buy_and_hold"},
            **overrides,
        )
    )


def test_next_close_accounting_and_benchmark():
    run = evaluate(inputs([100, 200, 100]))
    assert run.equity_curve[0]["quantity"] == "0"
    assert run.fills[0]["price"] == "200"
    assert Decimal(run.metrics["total_return"]) == Decimal("-0.5")
    assert Decimal(run.metrics["benchmark_return"]) == 0
    assert Decimal(run.metrics["max_drawdown"]) == Decimal("-0.5")
    assert run.metrics["closed_trades"] == 0
    assert run.metrics["win_rate"] is None
    assert run.metrics["sharpe_ratio"] == pytest.approx(-(126**0.5))


def test_costs_and_realized_trade_statistics():
    data = inputs([100, 110, 120, 80, 70]).model_dump()
    data["strategy"] = {"name": "sma", "fast": 1, "slow": 2}
    data["fee_bps"], data["slippage_bps"] = "10", "20"
    run = evaluate(SimulationInput.model_validate(data))
    quantity = Decimal(1000) / (Decimal(120) * Decimal("1.002") * Decimal("1.001"))
    ending = quantity * Decimal(70) * Decimal("0.998") * Decimal("0.999")
    assert Decimal(run.metrics["ending_equity"]) == pytest.approx(ending)
    assert run.metrics["losses"] == 1
    assert run.metrics["wins"] == 0
    assert run.metrics["win_rate"] == 0
    assert Decimal(run.metrics["realized_pnl"]) == pytest.approx(ending - 1000)
    assert run.metrics["unrealized_pnl"] == "0"
    assert [f["decision_index"] for f in run.fills] == [1, 3]


def test_future_prices_cannot_change_earlier_decisions():
    short = evaluate(inputs([100, 110, 120]))
    long = evaluate(inputs([100, 110, 120, 1, 9999]))
    assert short.decisions == long.decisions[:3]
    assert short.equity_curve == long.equity_curve[:3]
    assert short.dataset_hash != long.dataset_hash
    assert evaluate(inputs([100, 110, 120])).dataset_hash == short.dataset_hash


def test_flat_and_short_series():
    for prices in ([100], [100, 100], [100, 100, 100]):
        metrics = evaluate(inputs(prices)).metrics
        assert metrics["sharpe_ratio"] is None
        assert Decimal(metrics["max_drawdown"]) == 0
        assert Decimal(metrics["total_return"]) == 0


@pytest.mark.parametrize("change", ["alignment", "future", "duplicate", "adjustment", "nan"])
def test_invalid_inputs(change):
    data = inputs([100, 110]).model_dump(mode="json")
    if change == "alignment":
        data["benchmark"]["bars"].pop()
    elif change == "future":
        for key in ("history", "benchmark"):
            data[key]["bars"][-1]["timestamp"] = "2099-01-01T21:00:00Z"
    elif change == "duplicate":
        data["history"]["bars"][1] = data["history"]["bars"][0]
    elif change == "adjustment":
        data["benchmark"]["adjustment"] = "raw"
    else:
        data["fee_bps"] = "NaN"
    with pytest.raises(ValidationError):
        SimulationInput.model_validate(data)


def test_paper_restart_conflicts_and_backtest_parity(tmp_path):
    settings = Settings(_env_file=None, database_url=f"sqlite:///{tmp_path / 'sim.db'}")
    full = inputs([100, 110, 80]).model_dump(mode="json")
    seed = inputs([100]).model_dump(mode="json")
    with TestClient(create_app(settings)) as client:
        response = client.post("/paper-sessions", json=seed)
        assert response.status_code == 201
        run = response.json()
    with TestClient(create_app(settings)) as client:
        assert client.get(f"/simulations/{run['id']}").json() == run
        for i in (1, 2):
            body = {
                "expected_revision": i - 1,
                "bar": full["history"]["bars"][i],
                "benchmark_bar": full["benchmark"]["bars"][i],
            }
            response = client.post(f"/paper-sessions/{run['id']}/bars", json=body)
            assert response.status_code == 200
            assert client.post(f"/paper-sessions/{run['id']}/bars", json=body).status_code == 409
        paper = response.json()
        backtest = client.post("/backtests", json=full).json()
        for key in ("metrics", "decisions", "fills", "equity_curve", "dataset_hash"):
            assert paper[key] == backtest[key]
        assert client.post(f"/paper-sessions/{backtest['id']}/bars", json=body).status_code == 409
        body["expected_revision"] = 2
        assert client.post(f"/paper-sessions/{run['id']}/bars", json=body).status_code == 422
        assert client.get(f"/simulations/{run['id']}").json() == paper
