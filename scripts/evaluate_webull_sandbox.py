"""Read-only retail sandbox feasibility probe; no order or subscription mutation."""

import argparse
import importlib.metadata
import json
import logging
import os
from datetime import UTC, datetime
from pathlib import Path


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--env-file", type=Path, required=True)
    parser.add_argument("--report-file", type=Path, required=True)
    args = parser.parse_args()
    args.env_file = args.env_file.resolve()
    args.report_file = args.report_file.resolve()
    root = Path(__file__).resolve().parents[1]
    if any(p.resolve().is_relative_to(root) for p in (args.env_file, args.report_file)):
        parser.error("Private inputs and reports must stay outside repository")
    # Suppress SDK request/response dumps before imports; put SDK log files privately.
    logging.disable(logging.CRITICAL)
    os.chdir(args.env_file.resolve().parent)
    from dotenv import dotenv_values
    from webull.core.client import ApiClient
    from webull.core.exception.exceptions import ClientException, ServerException
    from webull.data.data_client import DataClient
    from webull.trade.trade_client import TradeClient

    values = dotenv_values(args.env_file.resolve())
    key, secret = values.get("AIL_WEBULL_APP_KEY"), values.get("AIL_WEBULL_APP_SECRET")
    if not key or not secret:
        parser.error("Required sandbox credential variables absent")
    api = ApiClient(key, secret, "us")
    api.add_endpoint("us", "api.sandbox.webull.com")
    trade, data = TradeClient(api), DataClient(api)
    report = {
        "schema_version": "webull-retail-sandbox-feasibility-v1",
        "observed_at_utc": datetime.now(UTC).isoformat(),
        "sdk_version": importlib.metadata.version("webull-openapi-python-sdk"),
        "endpoint": "api.sandbox.webull.com",
        "order_mutations": 0,
        "execution_available": False,
        "trial_started": False,
        "account_bound": False,
        "probes": {},
    }

    def probe(name, call):
        try:
            response = call()
            report["probes"][name] = {"http_status": response.status_code}
            if response.status_code == 200:
                return response.json()
        except (ClientException, ServerException, OSError, TimeoutError, ValueError, TypeError):
            # SDK exceptions may contain private identifiers or request bodies.
            report["probes"][name] = {"request_failed": True}
        return None

    accounts = probe("accounts", trade.account_v2.get_account_list)
    if not isinstance(accounts, list):
        accounts = []
    configured = values.get("AIL_WEBULL_ACCOUNT_ID") or values.get("$accountId")
    report["configured_account_matches"] = sum(a.get("account_id") == configured for a in accounts)
    report["account_count"] = len(accounts)
    report["equity_accounts"] = []
    for account in accounts:
        category = account.get("account_class")
        if category not in {"INDIVIDUAL_CASH", "INDIVIDUAL_MARGIN"}:
            continue
        identifier = account["account_id"]
        summary = {"account_class": category}
        balance = probe(
            category + "_balance",
            lambda identifier=identifier: trade.account_v2.get_account_balance(identifier),
        )
        if isinstance(balance, dict):
            for field in (
                "total_asset_currency",
                "total_net_liquidation_value",
                "total_cash_balance",
            ):
                summary[field] = balance.get(field)
            summary["settled_cash_field_present"] = any(
                "settled_cash" in asset for asset in balance.get("account_currency_assets", [])
            )
        positions = probe(
            category + "_positions",
            lambda identifier=identifier: trade.account_v2.get_account_position(identifier),
        )
        orders = probe(
            category + "_open_orders",
            lambda identifier=identifier: trade.order_v3.get_order_open(identifier),
        )
        summary["positions_count"] = len(positions) if isinstance(positions, list) else None
        summary["open_orders_count"] = len(orders) if isinstance(orders, list) else None
        activities = probe(
            category + "_cash_activities",
            lambda identifier=identifier: trade.activity.get_activities(identifier),
        )
        summary["activity_response_available"] = activities is not None
        report["equity_accounts"].append(summary)
    instrument = probe(
        "SCHB_instrument", lambda: data.instrument.get_instrument(["SCHB"], "US_ETF")
    )
    report["instrument_response_available"] = instrument is not None
    snapshot = probe("SCHB_snapshot", lambda: data.market_data.get_snapshot(["SCHB"], "US_ETF"))
    quotes = probe("SCHB_quotes", lambda: data.market_data.get_quotes("SCHB", "US_ETF"))
    report["snapshot_response_available"] = snapshot is not None
    report["quotes_response_available"] = quotes is not None
    report["market_status_verified"] = False
    report["real_time_entitlement_verified"] = False
    report["accounting_completeness_verified"] = False
    args.report_file.resolve().write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2))
    return 0 if report["probes"]["accounts"].get("http_status") == 200 else 1


if __name__ == "__main__":
    raise SystemExit(main())
