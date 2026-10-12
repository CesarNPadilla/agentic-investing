"""Read-only Alpaca paper account preflight; never submits or cancels orders."""
import argparse
import json
from datetime import UTC, datetime
from pathlib import Path

import httpx
from dotenv import dotenv_values

PAPER_URL = "https://paper-api.alpaca.markets"


def preflight(env_file: Path, *, transport=None):
    values = dotenv_values(env_file)
    key = values.get("AIL_ALPACA_API_KEY")
    secret = values.get("AIL_ALPACA_API_SECRET")
    report = {"checked_at_utc": datetime.now(UTC).isoformat(),
              "endpoint": PAPER_URL, "order_submission_available": False,
              "runtime_started": False, "account_access_verified": False,
              "empty_account_verified": False, "errors": []}
    if not isinstance(key, str) or not key.strip() or not isinstance(secret, str) or not secret.strip():
        report["errors"].append("Missing Alpaca credential fields")
        return report
    headers = {"APCA-API-KEY-ID": key, "APCA-API-SECRET-KEY": secret}
    try:
        # Fixed paper host, no redirects, no live endpoint or mutation methods.
        with httpx.Client(timeout=15, transport=transport, follow_redirects=False) as client:
            account = client.get(PAPER_URL + "/v2/account", headers=headers)
            if account.status_code != 200:
                report["errors"].append(f"Paper account read HTTP {account.status_code}")
                return report
            data = account.json()
            if not isinstance(data, dict) or not isinstance(data.get("status"), str):
                raise ValueError("Invalid account response")
            report["account_access_verified"] = True
            report["account_status"] = data["status"]
            flags = ("trading_blocked", "account_blocked", "trade_suspended_by_user")
            report["account_unblocked_verified"] = all(data.get(flag) is False for flag in flags)
            for flag in flags:
                report[flag] = data.get(flag) if isinstance(data.get(flag), bool) else None
            positions = client.get(PAPER_URL + "/v2/positions", headers=headers)
            orders = client.get(PAPER_URL + "/v2/orders", headers=headers,
                                params={"status": "open", "limit": 500, "nested": "true"})
            if positions.status_code != 200 or orders.status_code != 200:
                report["errors"].append("Paper inventory reads unavailable")
                return report
            holdings, pending = positions.json(), orders.json()
            if not isinstance(holdings, list) or not isinstance(pending, list):
                raise ValueError("Invalid inventory response")
            report["positions_returned"] = len(holdings)
            report["open_orders_returned"] = len(pending)
            report["orders_may_be_truncated"] = len(pending) >= 500
            report["empty_account_verified"] = not holdings and not pending
    except (httpx.HTTPError, ValueError, TypeError):
        # Never print provider responses, URLs with tokens, or exception details.
        report["errors"].append("Paper preflight unavailable or invalid response")
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--env-file", type=Path, required=True)
    args = parser.parse_args()
    report = preflight(args.env_file)
    print(json.dumps(report, indent=2))
    return 0 if report["account_access_verified"] and not report["errors"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
