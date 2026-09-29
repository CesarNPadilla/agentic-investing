"""Read Webull production account data locally; this CLI cannot submit or manage orders."""

import argparse
import json
from pathlib import Path

from integrations.brokers.webull_production import (
    WebullProductionCredentials,
    WebullProductionError,
    WebullProductionReadOnly,
)


def _print_result(label, value):
    print(label)
    print(json.dumps(value, indent=2, default=str))


def _response_shape(value):
    if isinstance(value, dict):
        return {key: _response_shape(item) for key, item in value.items()}
    if isinstance(value, list):
        return {
            "type": "array",
            "items": _response_shape(value[0]) if value else "empty",
        }
    return type(value).__name__


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--env-file", required=True, type=Path)
    commands = parser.add_subparsers(dest="command", required=True)
    accounts = commands.add_parser("accounts", help="List production accounts locally")
    accounts.add_argument(
        "--shape-only",
        action="store_true",
        help="Print response keys and JSON value types without private values",
    )
    for command in ("balance", "positions", "open-orders"):
        operation = commands.add_parser(command, help=f"Read production {command} data locally")
        operation.add_argument("--account-id", required=True)
        operation.add_argument(
            "--shape-only",
            action="store_true",
            help="Print response keys and JSON value types without private values",
        )
        if command == "open-orders":
            operation.add_argument("--pagination-key")

    arguments = parser.parse_args()
    try:
        credentials = WebullProductionCredentials.from_env_file(arguments.env_file)
        access = WebullProductionReadOnly(
            credentials.app_key.get_secret_value(),
            credentials.app_secret.get_secret_value(),
        )
        if arguments.command == "accounts":
            result = access.list_accounts()
        elif arguments.command == "balance":
            result = access.get_balance(arguments.account_id)
        elif arguments.command == "positions":
            result = access.get_positions(arguments.account_id)
        else:
            result = access.get_open_orders_page(
                arguments.account_id,
                getattr(arguments, "pagination_key", None),
            )
        if arguments.shape_only:
            _print_result("Webull production response shape:", _response_shape(result))
        else:
            _print_result("Webull production response (keep this output private):", result)
        return 0
    except WebullProductionError as exc:
        parser.exit(1, f"Production read failed: {exc}\n")
    except (OSError, ValueError) as exc:
        parser.exit(2, f"Production command failed validation: {exc}\n")


if __name__ == "__main__":
    raise SystemExit(main())