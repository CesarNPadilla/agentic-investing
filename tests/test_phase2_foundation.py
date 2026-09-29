import json

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from pydantic import SecretStr

from api.broker import broker_read_router
from api.config import Settings
from api.main import create_app
from database.repository import SQLReportRepository
from portfolio.intelligence import analyze_portfolio
from portfolio.storage import PortfolioObservation, PortfolioStore, ThesisInput
from portfolio.theses import PositionThesis
from risk.policy import InvestmentPolicy, load_investment_policy
from tests.test_investment_policy import NOW, replace
from tests.test_investment_policy import inputs as shared_inputs
from tests.test_policy_v02 import series
from tests.test_portfolio_intelligence import holding


@pytest.mark.parametrize(
    "payload",
    [
        "not-json",
        '{"production_trading":true}',
        '{"max_daily_loss":-1}',
        '{"version":"investment-policy-v3"}',
        '{"unexpected":"private-marker"}',
    ],
)
def test_invalid_policy_file_stops_startup_without_echoing_values(tmp_path, payload):
    path = tmp_path / "policy.json"
    path.write_text(payload)
    settings = Settings(
        _env_file=None,
        investment_policy_file=path,
        database_url="sqlite:///" + str(tmp_path / "unused.db"),
    )
    with pytest.raises(ValueError, match="Investment policy file is unreadable or invalid") as exc:
        create_app(settings)
    assert payload not in str(exc.value)
    assert not (tmp_path / "unused.db").exists()


def test_missing_policy_file_never_falls_back(tmp_path):
    with pytest.raises(ValueError, match="unreadable or invalid"):
        load_investment_policy(tmp_path / "missing.json")
    assert load_investment_policy(None) == InvestmentPolicy()


def test_policy_file_configures_research_without_expanding_purchase_scope(tmp_path):
    path = tmp_path / "policy.json"
    path.write_text(json.dumps({"research_universe": [], "new_purchase_allowlist": []}))
    settings = Settings(
        _env_file=None,
        investment_policy_file=path,
        database_url="sqlite:///" + str(tmp_path / "research.db"),
    )
    with TestClient(create_app(settings)) as client:
        assert client.post("/research/AAPL").status_code == 403
        assert client.get("/health").json()["live_trading_enabled"] is False
    policy = load_investment_policy(path)
    assert not policy.new_purchase_allowlist and policy.max_daily_loss is None
    with pytest.raises(ValueError, match="one investment policy source"):
        create_app(settings, investment_policy=InvestmentPolicy())


@pytest.fixture
def local_api(tmp_path):
    repository = SQLReportRepository("sqlite:///" + str(tmp_path / "portfolio.db"))
    repository.initialize()
    store = PortfolioStore(repository.engine)
    policy, _, state, _, _ = shared_inputs.__wrapped__()
    state = replace(state, positions=(holding(),))
    observation = PortfolioObservation(
        policy=policy,
        state=state,
        intelligence=analyze_portfolio(state, policy),
        performance_evidence=series(),
    )
    store.save(observation)
    app = FastAPI()

    def forbidden_reader():
        raise AssertionError("Local metadata operations must not load the broker")

    app.include_router(broker_read_router(forbidden_reader, SecretStr("x" * 32), store, policy))
    with TestClient(app) as client:
        yield client, store, observation, {"Authorization": "Bearer " + "x" * 32}
    repository.close()


def test_incremental_analysis_preserves_evidence_and_explicit_clear_is_auditable(local_api):
    client, store, observation, headers = local_api
    base = "/broker/portfolio/"
    url = base + observation.id + "/analysis"
    assert client.post(url, json={}).status_code == 401
    references = [
        {
            "symbol": "VOO",
            "source": "fixture",
            "as_of": NOW.isoformat(),
            "valid_until": NOW.isoformat(),
            "verified": True,
            "security_type": "etf",
        }
    ]
    response = client.post(url, json={"references": references}, headers=headers)
    assert response.status_code == 200, response.text
    enriched = response.json()
    assert enriched["state"][
        "experimental_attribution"
    ] == observation.state.experimental_attribution.model_dump(mode="json")
    assert enriched["performance_evidence"] == observation.performance_evidence.model_dump(
        mode="json"
    )
    assert enriched["derived_from_id"] == observation.id
    again = client.post(base + enriched["id"] + "/analysis", json={}, headers=headers).json()
    assert again["reference_data"] == enriched["reference_data"]
    assert again["performance_evidence"] == enriched["performance_evidence"]
    clear = client.post(
        base + again["id"] + "/analysis",
        json={"experimental_attribution": None, "references": [], "performance_evidence": None},
        headers=headers,
    ).json()
    assert clear["state"]["experimental_attribution"] is None
    assert not clear["intelligence"]["experimental_capital"]["valid"]
    assert clear["reference_data"] == [] and clear["performance_evidence"] is None
    assert store.get(enriched["id"]).reference_data
    assert store.get(observation.id).performance_evidence is not None


def test_thesis_history_is_authenticated_paginated_and_retained(local_api):
    client, store, _, headers = local_api
    original = PositionThesis(account_id="fixture", symbol="VOO")
    store.save_thesis(ThesisInput(expected_revision=0, thesis=original))
    store.save_thesis(
        ThesisInput(
            expected_revision=1,
            thesis=replace(original, current_thesis="Reviewed present-day rationale"),
        )
    )
    url = "/broker/accounts/fixture/theses/voo/history"
    assert client.get(url).status_code == 401
    first = client.get(url, params={"limit": 1}, headers=headers).json()
    assert first[0]["revision"] == 1
    assert first[0]["thesis"]["current_thesis"] is None
    second = client.get(url, params={"after_revision": 1}, headers=headers).json()
    assert second[0]["revision"] == 2
    assert second[0]["thesis"]["original_thesis_status"] == "UNKNOWN"
    assert client.get(url, params={"limit": 501}, headers=headers).status_code == 422
    assert client.get(url, params={"after_revision": -1}, headers=headers).status_code == 422
    assert client.get(url.replace("fixture", "another-account"), headers=headers).json() == []
    assert client.get(url, params={"after_revision": 2}, headers=headers).json() == []
