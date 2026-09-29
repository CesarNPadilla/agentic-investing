from datetime import UTC, datetime, timedelta
from decimal import Decimal
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from agents.research import ResearchOrchestrator
from api.config import Settings
from api.main import create_app
from market_data.base import ProviderUnavailable
from market_data.models import Quote
from market_data.sample import SampleMarketDataProvider
from risk.research import quote_warnings


@pytest.fixture
def settings(tmp_path):
    return Settings(_env_file=None, database_url=f"sqlite:///{tmp_path / 'test.db'}")


def test_report_persists_across_application_restart(settings):
    with TestClient(create_app(settings)) as client:
        response = client.post("/research/aapl")
        assert response.status_code == 201
        report = response.json()
        assert report["symbol"] == "AAPL"
        assert report["quote"]["price"] == "100.00"
        assert report["quote"]["is_sample"] is True
        assert report["status"] == "partial"
        assert report["missing_data"]
        assert report["bull_case"] == []
        assert any("Synthetic" in warning for warning in report["risks"])
    with TestClient(create_app(settings)) as client:
        assert client.get(f"/reports/{report['id']}").json() == report
        assert client.get("/ready").status_code == 200


def test_api_validation_and_absent_execution_routes(settings):
    with TestClient(create_app(settings)) as client:
        assert client.get("/health").json()["trading_enabled"] is False
        assert client.post("/research/MSFT").status_code == 404
        assert client.post("/research/123").status_code == 422
        assert client.get("/reports/not-a-uuid").status_code == 422
        assert client.get(f"/reports/{uuid4()}").status_code == 404
        assert client.post("/orders", json={}).status_code == 404
        assert client.get("/broker/accounts").status_code == 404
        paths = set(client.get("/openapi.json").json()["paths"])
        assert paths == {
            "/health",
            "/ready",
            "/research/{symbol}",
            "/reports/{report_id}",
            "/backtests",
            "/paper-sessions",
            "/simulations/{run_id}",
            "/paper-sessions/{run_id}/bars",
        }


def test_broker_read_routes_require_dedicated_token_and_do_not_load_on_startup(settings):
    from portfolio.models import Account, CashBalance, Position

    class Reader:
        def __init__(self):
            self.calls = []

        def get_accounts(self):
            self.calls.append("accounts")
            return [Account(account_id="account-1", currency="USD")]

        def get_cash(self, account_id):
            self.calls.append(("cash", account_id))
            return [CashBalance(account_id=account_id, currency="USD", amount="25.00")]

        def get_positions(self, account_id):
            self.calls.append(("positions", account_id))
            return [Position(account_id=account_id, symbol="AAPL", quantity="0.5")]

    token = "b" * 32
    enabled_settings = Settings(
        _env_file=None,
        database_url=settings.database_url,
        broker_read_enabled=True,
        broker_read_token=token,
    )
    reader = Reader()
    with TestClient(create_app(enabled_settings, broker_reader=reader)) as client:
        assert reader.calls == []
        assert client.get("/broker/accounts").status_code == 401
        assert reader.calls == []
        headers = {"Authorization": f"Bearer {token}"}
        accounts = client.get("/broker/accounts", headers=headers)
        assert accounts.status_code == 200
        assert accounts.json() == [{"account_id": "account-1", "currency": "USD"}]
        assert client.get("/broker/accounts/account-1/cash", headers=headers).status_code == 200
        positions = client.get("/broker/accounts/account-1/positions", headers=headers)
        assert positions.status_code == 200
        assert positions.json() == [
            Position(account_id="account-1", symbol="AAPL", quantity="0.5").model_dump(mode="json")
        ]
    assert reader.calls == ["accounts", ("cash", "account-1"), ("positions", "account-1")]


@pytest.mark.parametrize(
    "overrides",
    [
        {"broker_read_enabled": True},
        {
            "broker_read_enabled": True,
            "broker_read_token": "a" * 32,
            "trading_enabled": True,
            "trading_agent_token": "a" * 32,
            "trading_approval_token": "h" * 32,
        },
    ],
)
def test_broker_read_requires_a_distinct_long_token(settings, overrides):
    with pytest.raises(ValidationError):
        Settings(_env_file=None, database_url=settings.database_url, **overrides)


def test_provider_is_replaceable(settings):
    class AlternateProvider:
        def get_quote(self, symbol):
            return Quote(
                symbol=symbol,
                price=Decimal("42.125"),
                currency="USD",
                as_of=datetime.now(UTC),
                source="test-provider",
                is_sample=True,
            )

    with TestClient(create_app(settings, AlternateProvider())) as client:
        response = client.post("/research/MSFT")
        assert response.status_code == 201
        assert response.json()["quote"]["source"] == "test-provider"
        assert response.json()["quote"]["price"] == "42.125"


def test_provider_failure_is_explicit_and_does_not_leak_details(settings):
    class FailedProvider:
        def get_quote(self, symbol):
            raise ProviderUnavailable("private provider diagnostics")

    with TestClient(create_app(settings, FailedProvider())) as client:
        response = client.post("/research/AAPL")
        assert response.status_code == 503
        assert "private" not in response.text


def test_provider_symbol_mismatch_is_rejected():
    with pytest.raises(ValueError, match="different symbol"):

        class WrongProvider:
            def get_quote(self, symbol):
                return SampleMarketDataProvider().get_quote("AAPL")

        ResearchOrchestrator(WrongProvider()).research("MSFT")


@pytest.mark.parametrize(
    "overrides",
    [
        {"mode": "live"},
        {"mode": "paper"},
        {"market_provider": "robinhood"},
        {"llm_provider": "enabled"},
    ],
)
def test_unsupported_modes_fail_closed(overrides):
    with pytest.raises(ValidationError):
        Settings(_env_file=None, **overrides)


def test_research_mode_cannot_be_changed_by_environment(monkeypatch):
    monkeypatch.setenv("AIL_MODE", "live")
    with pytest.raises(ValidationError):
        Settings(_env_file=None)


@pytest.mark.parametrize("price", ["0", "-1", "NaN", "Infinity"])
def test_invalid_prices_are_rejected(price):
    values = SampleMarketDataProvider().get_quote("AAPL").model_dump()
    values["price"] = price
    with pytest.raises(ValidationError):
        Quote.model_validate(values)


def test_naive_timestamp_is_rejected():
    values = SampleMarketDataProvider().get_quote("AAPL").model_dump()
    values["as_of"] = datetime(2026, 1, 1)  # noqa: DTZ001 - deliberately invalid input
    with pytest.raises(ValidationError):
        Quote.model_validate(values)


def test_stale_and_future_data_are_flagged():
    quote = SampleMarketDataProvider().get_quote("AAPL")
    assert any(
        "24 hours" in warning for warning in quote_warnings(quote, quote.as_of + timedelta(days=2))
    )
    assert any(
        "future" in warning for warning in quote_warnings(quote, quote.as_of - timedelta(seconds=1))
    )
