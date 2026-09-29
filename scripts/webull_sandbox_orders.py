"""Preview and manage explicit, small Webull sandbox equity limit orders."""

import argparse
import json
from pathlib import Path
from uuid import UUID, uuid4

from pydantic import ValidationError

from integrations.brokers.orders import LimitOrder
from integrations.brokers.webull_sandbox import (
    WebullSandboxAccess,
    WebullSandboxCredentials,
    WebullSandboxError,
)


def _print_result(label, value):
    print(label)
    print(json.dumps(value, indent=2, default=str))


def _add_account(parser):
    parser.add_argument("--account-id", required=True)


def _add_order(parser):
    _add_account(parser)
    parser.add_argument("--symbol", choices=("AAPL", "MSFT", "SPY"), required=True)
    parser.add_argument("--quantity", required=True)
    parser.add_argument("--limit-price", required=True)
    parser.add_argument("--client-order-id", type=UUID, default=uuid4())


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--env-file", required=True, type=Path)
    commands = parser.add_subparsers(dest="command", required=True)

    commands.add_parser("accounts", help="List sandbox accounts locally")
    preview = commands.add_parser("preview", help="Preview a sandbox limit order only")
    _add_order(preview)
    place = commands.add_parser("place", help="Preview, confirm, then place a sandbox order")
    _add_order(place)
    status = commands.add_parser("status", help="Get a sandbox order's status")
    _add_account(status)
    status.add_argument("--client-order-id", type=UUID, required=True)
    cancel = commands.add_parser("cancel", help="Review and cancel a sandbox order")
    _add_account(cancel)
    cancel.add_argument("--client-order-id", type=UUID, required=True)

    arguments = parser.parse_args()
    try:
        credentials = WebullSandboxCredentials(_env_file=arguments.env_file)
        access = WebullSandboxAccess(
            credentials.app_key.get_secret_value(),
            credentials.app_secret.get_secret_value(),
        )
        if arguments.command == "accounts":
            _print_result("Webull sandbox account list (keep this output private):", access.list_accounts())
            return 0
        if arguments.command in {"preview", "place"}:
            order = LimitOrder(
                account_id=arguments.account_id,
                client_order_id=arguments.client_order_id,
                symbol=arguments.symbol,
                side="buy",
                quantity=arguments.quantity,
                limit_price=arguments.limit_price,
            )
            _print_result(
                "Exact sandbox order:",
                {
                    "environment": "sandbox",
                    "client_order_id": order.client_order_id.hex,
                    "symbol": order.symbol,
                    "side": order.side,
                    "quantity": str(order.quantity),
                    "limit_price": str(order.limit_price),
                    "notional": str(order.quantity * order.limit_price),
                    "order_type": order.order_type,
                    "time_in_force": order.time_in_force,
                    "session": "CORE",
                },
            )
            preview_result = access.preview_order(order)
            _print_result("Webull sandbox preview response:", preview_result)
            if arguments.command == "preview":
                print("Preview only; no order was submitted.")
                return 0
            if input("Type PLACE SANDBOX ORDER to submit this exact order: ") != "PLACE SANDBOX ORDER":
                print("Not submitted.")
                return 1
            _print_result("Webull sandbox place response:", access.place_order(order))
            return 0
        if arguments.command == "status":
            _print_result(
                "Webull sandbox order status:",
                access.get_order(arguments.account_id, arguments.client_order_id),
            )
            return 0
        current = access.get_order(arguments.account_id, arguments.client_order_id)
        _print_result("Current sandbox order status:", current)
        if input("Type CANCEL SANDBOX ORDER to cancel this exact order: ") != "CANCEL SANDBOX ORDER":
            print("Not cancelled.")
            return 1
        _print_result(
            "Webull sandbox cancel response:",
            access.cancel_order(arguments.account_id, arguments.client_order_id),
        )
        return 0
    except WebullSandboxError as exc:
        parser.exit(1, f"Sandbox API request failed: {exc}\n")
    except (OSError, ValidationError, ValueError) as exc:
        parser.exit(2, f"Sandbox command failed validation: {exc}\n")


if __name__ == "__main__":
    raise SystemExit(main())