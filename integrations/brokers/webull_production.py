"""Read-only Webull production account access; no order mutations are exposed."""

import logging
import os
from collections.abc import Callable
from decimal import Decimal
from pathlib import Path

from pydantic import BaseModel, ConfigDict, SecretStr, ValidationError

from integrations.brokers.base import AccountNotFound, BrokerUnavailable
from portfolio.models import Account, CashBalance, Position

WEBULL_PRODUCTION_API_ENDPOINT = "api.webull.com"
WEBULL_PRODUCTION_TOKEN_CACHE = Path("AgenticInvesting") / "webull-production-token"


class WebullProductionError(RuntimeError):
    pass


class WebullProductionCredentials(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    app_key: SecretStr
    app_secret: SecretStr

    @classmethod
    def from_env_file(cls, env_file: Path):
        try:
            from dotenv import dotenv_values
        except ImportError:
            raise WebullProductionError(
                "Install the optional Webull SDK support to load production credentials"
            ) from None

        values = dotenv_values(env_file)
        app_key = values.get("AIL_WEBULL_APP_KEY")
        app_secret = values.get("AIL_WEBULL_APP_SECRET")
        if not isinstance(app_key, str) or not app_key.strip():
            raise WebullProductionError("Production App Key is missing from the specified file")
        if not isinstance(app_secret, str) or not app_secret.strip():
            raise WebullProductionError("Production App Secret is missing from the specified file")
        return cls(app_key=app_key, app_secret=app_secret)


def _create_trade_client(app_key: str, app_secret: str, endpoint: str):
    try:
        from webull.core.client import ApiClient
        from webull.core.exception.exceptions import ClientException, ServerException
        from webull.trade.trade_client import TradeClient
    except ImportError:
        raise WebullProductionError(
            "Install the optional Webull SDK support to use production reads"
        ) from None

    local_app_data = os.environ.get("LOCALAPPDATA")
    if not local_app_data:
        raise WebullProductionError(
            "LOCALAPPDATA is not set; refusing to store the production token in the workspace"
        )

    api_client = ApiClient(app_key, app_secret, "us")
    api_client.set_stream_logger(log_level=logging.CRITICAL)
    api_client._file_logger_set = True
    api_client.set_token_dir(str(Path(local_app_data) / WEBULL_PRODUCTION_TOKEN_CACHE))
    api_client.add_endpoint("us", endpoint)
    try:
        return TradeClient(api_client)
    except (ClientException, ServerException, OSError, TimeoutError, ValueError) as exc:
        error_code = getattr(exc, "error_code", None)
        if error_code == "ERROR_CHECK_TOKEN":
            raise WebullProductionError(
                "Webull production token is expired or requires verification. The production "
                "token cache is separate from sandbox; verify the production API token in the "
                "Webull app, then retry."
            ) from None
        if error_code:
            raise WebullProductionError(
                f"Webull production client initialization failed (code {error_code})"
            ) from None
        raise WebullProductionError("Webull production client initialization failed") from None


class WebullProductionReadOnly:
    def __init__(
        self,
        app_key: str,
        app_secret: str,
        *,
        trade_client=None,
        client_factory: Callable[[str, str, str], object] = _create_trade_client,
    ):
        if not app_key.strip() or not app_secret.strip():
            raise ValueError("Webull production credentials are required")
        self._trade_client = (
            trade_client
            if trade_client is not None
            else client_factory(app_key, app_secret, WEBULL_PRODUCTION_API_ENDPOINT)
        )

    def list_accounts(self):
        return self._request_json(self._call_sdk(self._trade_client.account_v2.get_account_list))

    def get_balance(self, account_id: str):
        self._validate_account_id(account_id)
        return self._request_json(
            self._call_sdk(self._trade_client.account_v2.get_account_balance, account_id)
        )

    def get_positions(self, account_id: str):
        self._validate_account_id(account_id)
        return self._request_json(
            self._call_sdk(self._trade_client.account_v2.get_account_position, account_id)
        )

    def get_open_orders_page(self, account_id: str, pagination_key: str | None = None):
        self._validate_account_id(account_id)
        return self._request_json(
            self._call_sdk(
                self._trade_client.order_v3.list_order_open,
                account_id,
                pagination_key,
            )
        )

    def get_transactions_page(self, account_id, start_time, end_time, pagination_key=None):
        self._validate_account_id(account_id)
        return self._request_json(
            self._call_sdk(
                self._trade_client.activity.list_activities,
                account_id,
                None,
                start_time,
                end_time,
                pagination_key,
            )
        )

    @staticmethod
    def _validate_account_id(account_id: str):
        if not account_id.strip():
            raise ValueError("Production account ID is required")

    @staticmethod
    def _call_sdk(method, *args):
        expected_errors = (OSError, TimeoutError, TypeError, ValueError)
        sdk_server_exception = ()
        try:
            from webull.core.exception.exceptions import ClientException, ServerException
        except ImportError:
            pass
        else:
            expected_errors += (ClientException, ServerException)
            sdk_server_exception = (ServerException,)
        try:
            return method(*args)
        except expected_errors as exc:
            error_code = getattr(exc, "error_code", None)
            http_status = getattr(exc, "http_status", None)
            if sdk_server_exception and isinstance(exc, sdk_server_exception) and error_code:
                raise WebullProductionError(
                    f"Webull production API request failed (HTTP {http_status}, code {error_code})"
                ) from None
            raise WebullProductionError("Webull production API request failed") from None

    @staticmethod
    def _request_json(response):
        try:
            if response.status_code != 200:
                raise WebullProductionError("Webull production API request failed")
            payload = response.json()
            if not isinstance(payload, (dict, list)):
                raise WebullProductionError("Webull production returned an invalid response")
        except WebullProductionError:
            raise
        except (AttributeError, KeyError, OSError, TypeError, ValueError):
            raise WebullProductionError("Webull production API request failed") from None
        return payload


class WebullProductionBrokerReader:
    """Normalize production account, cash, and position reads to BrokerReader models."""

    def __init__(self, access: WebullProductionReadOnly):
        self._access = access

    def get_accounts(self) -> list[Account]:
        accounts = self._load_accounts()
        normalized = []
        for account in accounts:
            account_id = account["account_id"]
            balance = self._load_balance(account_id)
            currency = self._required_text(balance, "total_asset_currency")
            try:
                normalized.append(Account(account_id=account_id, currency=currency))
            except ValidationError:
                raise BrokerUnavailable("Webull production returned an invalid account") from None
        return normalized

    def get_positions(self, account_id: str) -> list[Position]:
        self._require_account(account_id)
        try:
            response = self._access.get_positions(account_id)
        except WebullProductionError:
            raise BrokerUnavailable("Webull production positions read failed") from None
        if not isinstance(response, list):
            raise BrokerUnavailable("Webull production returned invalid positions")
        try:
            return (
                [
                    Position(
                        account_id=account_id,
                        symbol=self._required_text(position, "symbol"),
                        quantity=self._required_text(position, "quantity"),
                        currency=position.get("currency"),
                        price=position.get("last_price") or None,
                        instrument_type=position.get("instrument_type"),
                        cost_basis=(
                            abs(Decimal(position["quantity"])) * Decimal(position["cost_price"])
                            if position.get("instrument_type") == "EQUITY"
                            and position.get("cost_price") not in (None, "")
                            else None
                        ),
                        market_value=(
                            Decimal(position["quantity"]) * Decimal(position["last_price"])
                            if position.get("instrument_type") == "EQUITY"
                            and position.get("last_price") not in (None, "")
                            else None
                        ),
                    )
                    for position in response
                    if isinstance(position, dict)
                ]
                if all(isinstance(position, dict) for position in response)
                else self._invalid_positions()
            )
        except (ValidationError, ArithmeticError, TypeError, ValueError):
            raise BrokerUnavailable("Webull production returned invalid positions") from None

    def get_cash(self, account_id: str) -> list[CashBalance]:
        self._require_account(account_id)
        balance = self._load_balance(account_id)
        assets = balance.get("account_currency_assets")
        if not isinstance(assets, list):
            raise BrokerUnavailable("Webull production returned invalid cash balances")
        try:
            return (
                [
                    CashBalance(
                        account_id=account_id,
                        currency=self._required_text(asset, "currency"),
                        amount=self._required_text(asset, "cash_balance"),
                        settled_cash=asset.get("settled_cash")
                        if asset.get("settled_cash") != ""
                        else None,
                        unsettled_cash=asset.get("unsettled_cash")
                        if asset.get("unsettled_cash") != ""
                        else None,
                        buying_power=asset.get("buying_power")
                        if asset.get("buying_power") != ""
                        else None,
                    )
                    for asset in assets
                    if isinstance(asset, dict)
                ]
                if all(isinstance(asset, dict) for asset in assets)
                else self._invalid_cash()
            )
        except ValidationError:
            raise BrokerUnavailable("Webull production returned invalid cash balances") from None

    def _load_accounts(self) -> list[dict[str, str]]:
        try:
            response = self._access.list_accounts()
        except WebullProductionError:
            raise BrokerUnavailable("Webull production account read failed") from None
        if not isinstance(response, list) or not all(isinstance(item, dict) for item in response):
            raise BrokerUnavailable("Webull production returned invalid accounts")
        accounts = []
        for item in response:
            account_id = item.get("account_id")
            if not isinstance(account_id, str) or not account_id.strip():
                raise BrokerUnavailable("Webull production returned an invalid account")
            accounts.append({"account_id": account_id})
        return accounts

    def read_state(self, *, history_start):
        from integrations.brokers.webull_portfolio import WebullPortfolioReader

        return WebullPortfolioReader(self._access).read_state(history_start=history_start)

    def get_open_orders(self, account_id):
        from integrations.brokers.webull_portfolio import WebullPortfolioReader

        self._require_account(account_id)
        return WebullPortfolioReader(self._access).get_open_orders(account_id)

    def get_transactions(self, account_id, start, end):
        from integrations.brokers.webull_portfolio import WebullPortfolioReader

        self._require_account(account_id)
        return WebullPortfolioReader(self._access).get_transactions(account_id, start, end)

    def _load_balance(self, account_id: str) -> dict:
        try:
            response = self._access.get_balance(account_id)
        except WebullProductionError:
            raise BrokerUnavailable("Webull production balance read failed") from None
        if not isinstance(response, dict):
            raise BrokerUnavailable("Webull production returned an invalid balance")
        return response

    def _require_account(self, account_id: str):
        if not isinstance(account_id, str) or not account_id.strip():
            raise AccountNotFound(account_id)
        if not any(account["account_id"] == account_id for account in self._load_accounts()):
            raise AccountNotFound(account_id)

    @staticmethod
    def _required_text(record: dict, field: str) -> str:
        value = record.get(field)
        if not isinstance(value, str) or not value.strip():
            raise BrokerUnavailable("Webull production response is missing a required field")
        return value

    @staticmethod
    def _invalid_positions():
        raise BrokerUnavailable("Webull production returned invalid positions")

    @staticmethod
    def _invalid_cash():
        raise BrokerUnavailable("Webull production returned invalid cash balances")
