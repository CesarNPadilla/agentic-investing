"""Paper-host order protocol qualification. Mutations only with httpx mock transport."""

from decimal import Decimal
from typing import Literal
from uuid import UUID

import httpx
from pydantic import BaseModel, ConfigDict, Field, model_validator

from risk.paper_state import PaperStateError

PAPER = "https://paper-api.alpaca.markets"


class PaperOrderIntent(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    client_order_id: UUID
    account_binding: str = Field(pattern=r"^[0-9a-f]{64}$")
    symbol: Literal["INTC"] = "INTC"
    side: Literal["buy", "sell"]
    quantity: int = Field(gt=0, strict=True)
    limit_price: Decimal = Field(gt=0, max_digits=12, decimal_places=2, allow_inf_nan=False)

    @model_validator(mode="after")
    def test_size(self):
        if not Decimal(25) <= self.quantity * self.limit_price <= Decimal(100):
            raise ValueError(
                "Dedicated account plumbing notional must meet $25 minimum and 10% cap"
            )
        return self

    def request(self):
        return {
            "client_order_id": str(self.client_order_id),
            "symbol": self.symbol,
            "side": self.side,
            "qty": str(self.quantity),
            "limit_price": str(self.limit_price),
            "type": "limit",
            "time_in_force": "day",
            "extended_hours": False,
        }


class PaperOrderProtocol:
    def __init__(self, key, secret, *, transport=None):
        if not key or not secret:
            raise ValueError("Credentials required")
        self._headers = {"APCA-API-KEY-ID": key, "APCA-API-SECRET-KEY": secret}
        self._transport = transport

    def _request(self, method, path, *, body=None, params=None):
        if method != "GET" and not isinstance(self._transport, httpx.MockTransport):
            raise PaperStateError(
                "Real order mutation remains blocked pending integrated qualification"
            )
        with httpx.Client(timeout=15, transport=self._transport, follow_redirects=False) as client:
            return client.request(
                method, PAPER + path, headers=self._headers, json=body, params=params
            )

    @staticmethod
    def validate(response, intent):
        if response.status_code != 200:
            raise PaperStateError("Order response uncertain or unavailable")
        row = response.json()
        if (
            row.get("client_order_id") != str(intent.client_order_id)
            or row.get("symbol") != intent.symbol
            or row.get("side") != intent.side
            or row.get("type") != "limit"
            or row.get("time_in_force") != "day"
            or Decimal(str(row.get("qty"))) != intent.quantity
            or Decimal(str(row.get("limit_price"))) != intent.limit_price
        ):
            raise PaperStateError("Broker order differs from bound intent")
        filled = Decimal(str(row.get("filled_qty")))
        if (
            not filled.is_finite()
            or not 0 <= filled <= intent.quantity
            or filled != filled.to_integral_value()
        ):
            raise PaperStateError("Invalid broker fill quantity")
        if row.get("status") not in {
            "new",
            "accepted",
            "pending_new",
            "partially_filled",
            "filled",
            "canceled",
            "expired",
            "rejected",
            "pending_cancel",
            "done_for_day",
        }:
            raise PaperStateError("Unqualified order status")
        if row["status"] == "filled" and filled != intent.quantity:
            raise PaperStateError("Filled order has incomplete quantity")
        return {
            "broker_order_id": str(UUID(row["id"])),
            "status": row["status"],
            "filled_quantity": str(filled),
            "execution_available": False,
        }

    def submit_fixture(self, intent):
        return self.validate(self._request("POST", "/v2/orders", body=intent.request()), intent)

    def lookup(self, intent):
        response = self._request(
            "GET",
            "/v2/orders:by_client_order_id",
            params={"client_order_id": str(intent.client_order_id)},
        )
        if response.status_code == 404:
            return None
        return self.validate(response, intent)

    def cancel_fixture(self, intent):
        response = self._request(
            "GET",
            "/v2/orders:by_client_order_id",
            params={"client_order_id": str(intent.client_order_id)},
        )
        self.validate(response, intent)
        broker_id = UUID(response.json()["id"])
        canceled = self._request("DELETE", f"/v2/orders/{broker_id}")
        if canceled.status_code != 204:
            raise PaperStateError("Cancel response uncertain")
        # An accepted cancellation is not terminal status or filled-cash reconciliation.
        return {"phase": "CANCEL_UNCERTAIN", "execution_available": False}
