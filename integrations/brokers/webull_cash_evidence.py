"""Selected retail sandbox cash observation; no broker mutation interface."""

import hashlib
from datetime import UTC, datetime
from decimal import Decimal, InvalidOperation

ENDPOINT = "api.sandbox.webull.com"


def account_binding(identifier):
    return hashlib.sha256(("WEBULL_RETAIL_SANDBOX\0" + identifier).encode()).hexdigest()


def _balance(payload):
    if payload.get("total_asset_currency") != "USD":
        raise ValueError("USD cash account required")
    assets = payload["account_currency_assets"]
    if not isinstance(assets, list) or len(assets) != 1 or assets[0].get("currency") != "USD":
        raise ValueError("Single USD currency asset required")
    fields = {
        "equity": payload["total_net_liquidation_value"],
        "cash": payload["total_cash_balance"],
        "settled": assets[0]["settled_cash"],
        "unsettled": assets[0]["unsettled_cash"],
    }
    numbers = {}
    for key, value in fields.items():
        if isinstance(value, bool):
            raise TypeError("Numeric balance required")
        amount = Decimal(str(value))
        if not amount.is_finite() or amount < 0 or (key == "equity" and amount == 0):
            raise ValueError("Invalid cash balance")
        numbers[key] = amount
    if numbers["settled"] + numbers["unsettled"] != numbers["cash"]:
        raise ValueError("Cash breakdown inconsistent")
    return numbers


class WebullCashEvidenceReader:
    def __init__(self, trade_client, selection, *, clock=lambda: datetime.now(UTC)):
        if (
            selection.get("environment") != "sandbox"
            or selection.get("endpoint") != ENDPOINT
            or selection.get("account_class") != "INDIVIDUAL_CASH"
            or selection.get("execution_available") is not False
            or selection.get("trial_started") is not False
        ):
            raise ValueError("Disabled cash sandbox selection required")
        identifier = selection.get("account_id")
        if not isinstance(identifier, str) or not identifier.strip():
            raise ValueError("Private account identifier required")
        if selection.get("account_binding_sha256") != account_binding(identifier):
            raise ValueError("Account binding mismatch")
        self._client, self._identifier, self._clock = trade_client, identifier, clock

    def observe(self):
        start = self._clock()
        if start.tzinfo is None or start.utcoffset() is None:
            raise ValueError("Aware source observation required")

        def read(method, *args):
            response = method(*args)
            if response.status_code != 200:
                raise ValueError("Sandbox source unavailable")
            return response.json()

        try:
            accounts = read(self._client.account_v2.get_account_list)
            if not isinstance(accounts, list):
                raise TypeError("Account inventory required")
            matches = [a for a in accounts if a.get("account_id") == self._identifier]
            if (
                len(matches) != 1
                or matches[0].get("account_class") != "INDIVIDUAL_CASH"
                or matches[0].get("account_type") != "CASH"
            ):
                raise ValueError("Selected cash account not uniquely discovered")
            first = _balance(read(self._client.account_v2.get_account_balance, self._identifier))
            positions = read(self._client.account_v2.get_account_position, self._identifier)
            orders = read(self._client.order_v3.get_order_open, self._identifier)
            second = _balance(read(self._client.account_v2.get_account_balance, self._identifier))
            if not isinstance(positions, list) or not isinstance(orders, list) or first != second:
                raise ValueError("Inventory or stable bracket unavailable")
            end = self._clock()
            if end.tzinfo is None or end.utcoffset() is None or end < start:
                raise ValueError("Receipt time invalid")
            return {
                "schema_version": "webull-bound-cash-observation-v1",
                "environment": "sandbox",
                "account_class": "INDIVIDUAL_CASH",
                "started_at_utc": start.isoformat(),
                "finished_at_utc": end.isoformat(),
                "observed_equity_usd": str(second["equity"]),
                "observed_cash_usd": str(second["cash"]),
                "reported_settled_cash_usd": str(second["settled"]),
                "reported_unsettled_cash_usd": str(second["unsettled"]),
                "positions_count": len(positions),
                "returned_open_orders_count": len(orders),
                "balance_bracket_stable": True,
                "blockers": [
                    "ACCOUNT_ACTIVITY_PUBLICATION_UNQUALIFIED",
                    "ACCOUNT_ASOF_UNQUALIFIED",
                    "MIDNIGHT_BASELINE_UNQUALIFIED",
                    "RUNTIME_INTEGRATION_PENDING",
                ]
                + (["EXISTING_EXPOSURE_HUMAN_REVIEW_REQUIRED"] if positions or orders else []),
                "experimental_sleeve_ceiling_usd": "1000",
                "execution_available": False,
                "trial_started": False,
            }
        except (KeyError, TypeError, ValueError, InvalidOperation):
            raise ValueError("Webull cash evidence unavailable or invalid") from None
