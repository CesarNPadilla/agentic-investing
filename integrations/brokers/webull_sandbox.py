"""Read-only Webull sandbox access check; production endpoints are never used."""

import logging
from collections.abc import Callable
from decimal import Decimal
from uuid import UUID

from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

from integrations.brokers.orders import LimitOrder

WEBULL_SANDBOX_API_ENDPOINT = "api.sandbox.webull.com"
SANDBOX_ORDER_NOTIONAL_LIMIT = Decimal(160)
SANDBOX_ALLOWED_SYMBOLS = frozenset({"AAPL", "MSFT", "SPY"})


def _suppress_sdk_request_dumps():
    logging.getLogger("webull.core.client").setLevel(logging.CRITICAL)


class WebullSandboxCredentials(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="AIL_WEBULL_", extra="ignore")
    app_key: SecretStr
    app_secret: SecretStr


class WebullSandboxError(RuntimeError):
    pass


def _create_trade_client(app_key: str, app_secret: str, endpoint: str):
    try:
        from webull.core.client import ApiClient
        from webull.trade.trade_client import TradeClient
    except ImportError:
        raise WebullSandboxError("Install the optional Webull SDK to use this check") from None

    _suppress_sdk_request_dumps()
    api_client = ApiClient(app_key, app_secret, "us")
    api_client.add_endpoint("us", endpoint)
    return TradeClient(api_client)


class WebullSandboxAccess:
    def __init__(
        self,
        app_key: str,
        app_secret: str,
        *,
        trade_client=None,
        client_factory: Callable[[str, str, str], object] = _create_trade_client,
    ):
        if not app_key.strip() or not app_secret.strip():
            raise ValueError("Webull sandbox credentials are required")
        self._trade_client = (
            trade_client
            if trade_client is not None
            else client_factory(app_key, app_secret, WEBULL_SANDBOX_API_ENDPOINT)
        )

    def verify_access(self) -> dict[str, str | bool]:
        payload = self.list_accounts()
        if not isinstance(payload, (dict, list)):
            raise WebullSandboxError("Webull sandbox returned an invalid response")
        return {"connected": True, "environment": "sandbox"}

    def list_accounts(self):
        return self._request_json(
            self._call_sdk(self._trade_client.account_v2.get_account_list)
        )

    def preview_order(self, order: LimitOrder):
        body = self._order_payload(order)
        return self._request_json(
            self._call_sdk(
                self._trade_client.order_v3.preview_order, order.account_id, [body]
            )
        )

    def place_order(self, order: LimitOrder):
        body = self._order_payload(order)
        return self._request_json(
            self._call_sdk(self._trade_client.order_v3.place_order, order.account_id, [body])
        )

    def get_order(self, account_id: str, client_order_id: UUID):
        if not account_id.strip():
            raise ValueError("Sandbox account ID is required")
        return self._request_json(
            self._call_sdk(
                self._trade_client.order_v3.get_order_detail,
                account_id,
                client_order_id.hex,
            )
        )

    def cancel_order(self, account_id: str, client_order_id: UUID):
        if not account_id.strip():
            raise ValueError("Sandbox account ID is required")
        return self._request_json(
            self._call_sdk(
                self._trade_client.order_v3.cancel_order,
                account_id,
                client_order_id.hex,
            )
        )

    @staticmethod
    def _order_payload(order: LimitOrder) -> dict[str, str]:
        if order.side != "buy":
            raise WebullSandboxError("Sandbox trial is restricted to buy orders")
        if order.symbol not in SANDBOX_ALLOWED_SYMBOLS:
            raise WebullSandboxError("Symbol is not enabled for sandbox trials")
        if order.quantity * order.limit_price > SANDBOX_ORDER_NOTIONAL_LIMIT:
            raise WebullSandboxError("Sandbox order exceeds the USD 160 notional cap")
        return {
            "client_order_id": order.client_order_id.hex,
            "combo_type": "NORMAL",
            "symbol": order.symbol,
            "instrument_type": "EQUITY",
            "market": "US",
            "order_type": "LIMIT",
            "limit_price": str(order.limit_price),
            "quantity": str(order.quantity),
            "support_trading_session": "CORE",
            "side": "BUY",
            "time_in_force": "DAY",
            "entrust_type": "QTY",
        }

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
            if sdk_server_exception and isinstance(exc, sdk_server_exception):
                if error_code == "OPENAPI_CAN_NOT_TRADING_FOR_FIXGW_NOT_READY_NIGHT":
                    raise WebullSandboxError(
                        WebullSandboxAccess._night_session_rejection_message()
                    ) from None
                if error_code:
                    raise WebullSandboxError(
                        f"Webull sandbox API request failed (HTTP {http_status}, code {error_code})"
                    ) from None
            raise WebullSandboxError("Webull sandbox API request failed") from None

    @staticmethod
    def _night_session_rejection_message() -> str:
        return (
            "Webull sandbox rejected this CORE order outside the available regular session. "
            "Do not switch this restricted tool to overnight trading. Check the order status "
            "before retrying during regular US market hours."
        )

    @staticmethod
    def _request_json(response):
        try:
            if response.status_code != 200:
                raise WebullSandboxError("Webull sandbox API request failed")
            payload = response.json()
            if not isinstance(payload, (dict, list)):
                raise WebullSandboxError("Webull sandbox returned an invalid response")
        except WebullSandboxError:
            raise
        except (AttributeError, KeyError, OSError, TypeError, ValueError):
            raise WebullSandboxError("Webull sandbox API request failed") from None
        return payload