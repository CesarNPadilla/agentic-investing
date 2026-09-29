from decimal import Decimal

import pytest
from pydantic import ValidationError

from integrations.brokers.base import AccountNotFound, BrokerReader
from integrations.brokers.orders import LimitOrder, OrderReceipt
from integrations.brokers.sample import SampleBrokerReader
from integrations.brokers.webull_sandbox import (
    WEBULL_SANDBOX_API_ENDPOINT,
    WebullSandboxAccess,
    WebullSandboxCredentials,
    WebullSandboxError,
)
from portfolio.models import Account, CashBalance, Position


def test_sample_reader_returns_consistent_normalized_data():
    reader: BrokerReader = SampleBrokerReader()
    account = reader.get_accounts()[0]
    position = reader.get_positions(account.account_id)[0]
    cash = reader.get_cash(account.account_id)[0]
    assert position.account_id == cash.account_id == account.account_id
    assert position.quantity == Decimal("2.5")
    assert cash.amount == Decimal("1000.00")
    assert cash.currency == account.currency == "USD"


@pytest.mark.parametrize("method", ["get_positions", "get_cash"])
def test_unknown_account_does_not_return_another_accounts_data(method):
    with pytest.raises(AccountNotFound):
        getattr(SampleBrokerReader(), method)("unknown-account")


def test_callers_cannot_modify_subsequent_reads():
    reader = SampleBrokerReader()
    accounts = reader.get_accounts()
    accounts.clear()
    account = reader.get_accounts()[0]
    with pytest.raises(ValidationError):
        account.currency = "EUR"
    positions = reader.get_positions(account.account_id)
    positions.clear()
    assert len(reader.get_positions(account.account_id)) == 1


@pytest.mark.parametrize("value", ["NaN", "Infinity", "-Infinity"])
def test_nonfinite_balances_and_quantities_are_rejected(value):
    with pytest.raises(ValidationError):
        Position(account_id="sample", symbol="AAPL", quantity=value)
    with pytest.raises(ValidationError):
        CashBalance(account_id="sample", currency="USD", amount=value)


def test_fractional_short_position_survives_json_roundtrip():
    position = Position(account_id="sample", symbol="AAPL", quantity=Decimal("-0.125"))
    assert Position.model_validate_json(position.model_dump_json()) == position


def test_order_adapter_contract_is_limit_day_only_and_idempotency_keyed():
    from datetime import UTC, datetime
    from uuid import uuid4

    order_id = uuid4()
    order = LimitOrder(
        account_id="synthetic-phase4",
        client_order_id=order_id,
        symbol="AAPL",
        side="buy",
        quantity="2",
        limit_price="100",
    )
    receipt = OrderReceipt(
        client_order_id=order_id,
        status="accepted",
        updated_at=datetime.now(UTC),
    )
    assert order.order_type == "limit" and order.time_in_force == "day"
    assert receipt.client_order_id == order.client_order_id
    with pytest.raises(ValidationError):
        LimitOrder.model_validate({**order.model_dump(mode="json"), "order_type": "market"})


def test_webull_sandbox_access_uses_fixed_sandbox_and_withholds_account_data():
    class Response:
        status_code = 200

        def json(self):
            return {"accounts": [{"account_id": "private-account-id"}]}

    class AccountAPI:
        def get_account_list(self):
            return Response()

    class TradeClient:
        account_v2 = AccountAPI()

    endpoints = []

    def client_factory(app_key, app_secret, endpoint):
        endpoints.append((app_key, app_secret, endpoint))
        return TradeClient()

    result = WebullSandboxAccess(
        "test-key",
        "test-secret",
        client_factory=client_factory,
    ).verify_access()
    assert result == {"connected": True, "environment": "sandbox"}
    assert "private-account-id" not in str(result)
    assert endpoints == [("test-key", "test-secret", WEBULL_SANDBOX_API_ENDPOINT)]


def test_webull_sandbox_failure_is_sanitized():
    class Response:
        status_code = 403
        text = "private response details"

    class AccountAPI:
        def get_account_list(self):
            return Response()

    class TradeClient:
        account_v2 = AccountAPI()

    with pytest.raises(WebullSandboxError, match="API request failed") as error:
        WebullSandboxAccess("test-key", "test-secret", trade_client=TradeClient()).verify_access()
    assert "private response details" not in str(error.value)


def test_webull_sandbox_sdk_error_is_sanitized():
    class AccountAPI:
        def get_account_list(self):
            raise ValueError("private network diagnostic")

    class TradeClient:
        account_v2 = AccountAPI()

    with pytest.raises(WebullSandboxError, match="API request failed") as error:
        WebullSandboxAccess("test-key", "test-secret", trade_client=TradeClient()).verify_access()
    assert "private network diagnostic" not in str(error.value)


def test_webull_night_gateway_error_is_explained_without_request_details():
    from integrations.brokers.webull_sandbox import WebullSandboxAccess

    message = WebullSandboxAccess._night_session_rejection_message()
    assert "outside the available regular session" in message
    assert "Do not switch this restricted tool to overnight trading" in message


def test_webull_sdk_server_error_is_mapped_without_leaking_response(monkeypatch):
    import sys
    from types import ModuleType

    from integrations.brokers.webull_sandbox import WebullSandboxAccess

    class ClientException(Exception):
        pass

    class ServerException(Exception):
        def __init__(self, error_code, error_msg, http_status, request_id):
            self.error_code = error_code
            self.error_msg = error_msg
            self.http_status = http_status
            self.request_id = request_id

    package_names = (
        "webull",
        "webull.core",
        "webull.core.exception",
    )
    for name in package_names:
        package = ModuleType(name)
        package.__path__ = []
        monkeypatch.setitem(sys.modules, name, package)
    exceptions = ModuleType("webull.core.exception.exceptions")
    exceptions.ClientException = ClientException
    exceptions.ServerException = ServerException
    monkeypatch.setitem(sys.modules, exceptions.__name__, exceptions)

    def rejected_order():
        raise ServerException(
            "OPENAPI_CAN_NOT_TRADING_FOR_FIXGW_NOT_READY_NIGHT",
            "private server message",
            417,
            "private-request-id",
        )

    with pytest.raises(WebullSandboxError, match="outside the available regular session") as error:
        WebullSandboxAccess._call_sdk(rejected_order)
    assert "private server message" not in str(error.value)
    assert "private-request-id" not in str(error.value)


def test_webull_sandbox_limit_order_preview_place_status_and_cancel():
    from uuid import uuid4

    class Response:
        status_code = 200

        def __init__(self, value):
            self.value = value

        def json(self):
            return self.value

    class OrderAPI:
        def __init__(self):
            self.calls = []

        def preview_order(self, account_id, orders):
            self.calls.append(("preview", account_id, orders))
            return Response({"preview": "ok"})

        def place_order(self, account_id, orders):
            self.calls.append(("place", account_id, orders))
            return Response({"order": "accepted"})

        def get_order_detail(self, account_id, client_order_id):
            self.calls.append(("status", account_id, client_order_id))
            return Response({"status": "working"})

        def cancel_order(self, account_id, client_order_id):
            self.calls.append(("cancel", account_id, client_order_id))
            return Response({"status": "cancelled"})

    order_api = OrderAPI()
    trade_client = type("TradeClient", (), {"order_v3": order_api})()
    access = WebullSandboxAccess("test-key", "test-secret", trade_client=trade_client)
    order_id = uuid4()
    order = LimitOrder(
        account_id="test-account",
        client_order_id=order_id,
        symbol="AAPL",
        side="buy",
        quantity="0.5",
        limit_price="100",
    )

    assert access.preview_order(order) == {"preview": "ok"}
    assert access.place_order(order) == {"order": "accepted"}
    assert access.get_order("test-account", order_id) == {"status": "working"}
    assert access.cancel_order("test-account", order_id) == {"status": "cancelled"}
    assert [call[0] for call in order_api.calls] == ["preview", "place", "status", "cancel"]
    order_body = order_api.calls[0][2][0]
    assert order_body["client_order_id"] == order_id.hex
    assert len(order_body["client_order_id"]) == 32
    assert order_body["order_type"] == "LIMIT"
    assert order_body["time_in_force"] == "DAY"
    assert order_body["support_trading_session"] == "CORE"


@pytest.mark.parametrize(
    ("symbol", "side", "quantity", "limit_price"),
    [
        ("GME", "buy", "1", "10"),
        ("AAPL", "sell", "1", "10"),
        ("AAPL", "buy", "2", "100"),
    ],
)
def test_webull_sandbox_rejects_unsupported_orders_before_api_call(
    symbol, side, quantity, limit_price
):
    from uuid import uuid4

    order = LimitOrder(
        account_id="test-account",
        client_order_id=uuid4(),
        symbol=symbol,
        side=side,
        quantity=quantity,
        limit_price=limit_price,
    )
    with pytest.raises(WebullSandboxError):
        WebullSandboxAccess._order_payload(order)


def test_webull_sandbox_credentials_load_only_expected_prefix(tmp_path):
    env_file = tmp_path / "webull.sandbox.env"
    env_file.write_text("AIL_WEBULL_APP_KEY=test-key\nAIL_WEBULL_APP_SECRET=test-secret\n")
    settings = WebullSandboxCredentials(_env_file=env_file)
    assert settings.app_key.get_secret_value() == "test-key"
    assert settings.app_secret.get_secret_value() == "test-secret"


def test_webull_production_reads_are_pinned_and_have_no_order_mutations():
    from integrations.brokers.webull_production import (
        WEBULL_PRODUCTION_API_ENDPOINT,
        WebullProductionReadOnly,
    )

    class Response:
        status_code = 200

        def __init__(self, value):
            self.value = value

        def json(self):
            return self.value

    class AccountAPI:
        def __init__(self):
            self.calls = []

        def get_account_list(self):
            self.calls.append(("accounts",))
            return Response([{"account_id": "private-account-id"}])

        def get_account_balance(self, account_id):
            self.calls.append(("balance", account_id))
            return Response({"cash": "private-balance"})

        def get_account_position(self, account_id):
            self.calls.append(("positions", account_id))
            return Response([])

    class OrderAPI:
        def __init__(self):
            self.calls = []

        def list_order_open(self, account_id, pagination_key):
            self.calls.append((account_id, pagination_key))
            return Response({"orders": [], "pagination_key": "next-page"})

    account_api = AccountAPI()
    order_api = OrderAPI()
    trade_client = type(
        "TradeClient",
        (),
        {"account_v2": account_api, "order_v3": order_api},
    )()
    endpoints = []

    def client_factory(app_key, app_secret, endpoint):
        endpoints.append((app_key, app_secret, endpoint))
        return trade_client

    access = WebullProductionReadOnly("prod-key", "prod-secret", client_factory=client_factory)
    assert access.list_accounts() == [{"account_id": "private-account-id"}]
    assert access.get_balance("account-1") == {"cash": "private-balance"}
    assert access.get_positions("account-1") == []
    assert access.get_open_orders_page("account-1", "cursor") == {
        "orders": [],
        "pagination_key": "next-page",
    }
    assert endpoints == [("prod-key", "prod-secret", WEBULL_PRODUCTION_API_ENDPOINT)]
    assert WEBULL_PRODUCTION_API_ENDPOINT == "api.webull.com"
    assert account_api.calls == [
        ("accounts",),
        ("balance", "account-1"),
        ("positions", "account-1"),
    ]
    assert order_api.calls == [("account-1", "cursor")]
    assert not hasattr(access, "place_order")
    assert not hasattr(access, "cancel_order")


def test_webull_production_credentials_load_only_from_explicit_file(tmp_path, monkeypatch):
    pytest.importorskip("dotenv")
    from integrations.brokers.webull_production import WebullProductionCredentials

    env_file = tmp_path / "webull.env"
    env_file.write_text(
        "AIL_WEBULL_APP_KEY=production-key\nAIL_WEBULL_APP_SECRET=production-secret\n"
    )
    monkeypatch.setenv("AIL_WEBULL_APP_KEY", "sandbox-key")
    monkeypatch.setenv("AIL_WEBULL_APP_SECRET", "sandbox-secret")

    credentials = WebullProductionCredentials.from_env_file(env_file)
    assert credentials.app_key.get_secret_value() == "production-key"
    assert credentials.app_secret.get_secret_value() == "production-secret"


def test_webull_production_uses_separate_token_cache_and_sanitizes_expiration(
    tmp_path, monkeypatch
):
    import sys
    from types import ModuleType

    from webull.core.exception.exceptions import ClientException

    from integrations.brokers.webull_production import (
        WEBULL_PRODUCTION_TOKEN_CACHE,
        WebullProductionError,
        _create_trade_client,
    )

    class ApiClient:
        def __init__(self, app_key, app_secret, region):
            self.token_dir = None
            self.endpoint = None

        def set_stream_logger(self, **kwargs):
            pass

        def set_token_dir(self, token_dir):
            self.token_dir = token_dir

        def add_endpoint(self, region, endpoint):
            self.endpoint = endpoint

    class TradeClient:
        def __init__(self, api_client):
            self.api_client = api_client

    client_module = ModuleType("webull.core.client")
    client_module.ApiClient = ApiClient
    trade_module = ModuleType("webull.trade.trade_client")
    trade_module.TradeClient = TradeClient
    monkeypatch.setitem(sys.modules, client_module.__name__, client_module)
    monkeypatch.setitem(sys.modules, trade_module.__name__, trade_module)
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))

    trade_client = _create_trade_client("key", "secret", "api.webull.com")
    expected_cache = tmp_path / WEBULL_PRODUCTION_TOKEN_CACHE
    assert trade_client.api_client.token_dir == str(expected_cache)
    assert trade_client.api_client.endpoint == "api.webull.com"

    class ExpiredTradeClient:
        def __init__(self, api_client):
            raise ClientException("ERROR_CHECK_TOKEN", "private token details")

    trade_module.TradeClient = ExpiredTradeClient
    with pytest.raises(
        WebullProductionError, match="token is expired or requires verification"
    ) as error:
        _create_trade_client("key", "secret", "api.webull.com")
    assert "private token details" not in str(error.value)


def test_webull_production_response_shape_omits_private_values():
    import json

    from scripts.webull_production_read import _response_shape

    response = {
        "data": [{"account_id": "private-id", "amount": "1234.56", "quantity": 2}],
        "currency": "USD",
    }
    shape = _response_shape(response)

    assert shape == {
        "data": {
            "type": "array",
            "items": {"account_id": "str", "amount": "str", "quantity": "int"},
        },
        "currency": "str",
    }
    assert "private-id" not in json.dumps(shape)
    assert "1234.56" not in json.dumps(shape)


def test_webull_production_broker_reader_normalizes_account_cash_and_positions():
    from integrations.brokers.webull_production import WebullProductionBrokerReader

    class Access:
        def list_accounts(self):
            return [{"account_id": "account-1", "account_type": "STOCK"}]

        def get_balance(self, account_id):
            assert account_id == "account-1"
            return {
                "total_asset_currency": "USD",
                "account_currency_assets": [
                    {"currency": "USD", "cash_balance": "84.25", "settled_cash": "80.00"},
                    {"currency": "CAD", "cash_balance": "10.00", "settled_cash": "10.00"},
                ],
            }

        def get_positions(self, account_id):
            assert account_id == "account-1"
            return [
                {"symbol": "AAPL", "quantity": "0.5", "currency": "USD"},
                {"symbol": "MSFT", "quantity": "2", "currency": "USD"},
            ]

    reader = WebullProductionBrokerReader(Access())
    assert reader.get_accounts() == [Account(account_id="account-1", currency="USD")]
    assert reader.get_cash("account-1") == [
        CashBalance(
            account_id="account-1",
            currency="USD",
            amount=Decimal("84.25"),
            settled_cash=Decimal(80),
        ),
        CashBalance(
            account_id="account-1",
            currency="CAD",
            amount=Decimal("10.00"),
            settled_cash=Decimal(10),
        ),
    ]
    assert reader.get_positions("account-1") == [
        Position(account_id="account-1", symbol="AAPL", quantity=Decimal("0.5"), currency="USD"),
        Position(account_id="account-1", symbol="MSFT", quantity=Decimal(2), currency="USD"),
    ]


def test_webull_production_broker_reader_rejects_unknown_accounts():
    from integrations.brokers.webull_production import WebullProductionBrokerReader

    class Access:
        def list_accounts(self):
            return [{"account_id": "known-account"}]

    reader = WebullProductionBrokerReader(Access())
    with pytest.raises(AccountNotFound):
        reader.get_positions("unknown-account")


@pytest.mark.parametrize("field", ["cash", "position"])
def test_webull_production_broker_reader_fails_closed_on_invalid_financial_fields(field):
    from integrations.brokers.base import BrokerUnavailable
    from integrations.brokers.webull_production import WebullProductionBrokerReader

    class Access:
        def list_accounts(self):
            return [{"account_id": "account-1"}]

        def get_balance(self, account_id):
            return {
                "total_asset_currency": "USD",
                "account_currency_assets": [{"currency": "USD", "cash_balance": "not-a-number"}],
            }

        def get_positions(self, account_id):
            return [{"symbol": "AAPL", "quantity": "NaN"}]

    reader = WebullProductionBrokerReader(Access())
    with pytest.raises(BrokerUnavailable):
        if field == "cash":
            reader.get_cash("account-1")
        else:
            reader.get_positions("account-1")
