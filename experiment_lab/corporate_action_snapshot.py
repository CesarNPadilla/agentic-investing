"""Read-only, immutable development/validation Alpaca action snapshot."""

import argparse
import hashlib
import json
from datetime import UTC, date, datetime
from pathlib import Path

import httpx

from experiment_lab.corporate_action_reconstruction import CUTOFF, SECURITIES
from experiment_lab.historical_fetch import MarketDataCredentials


def capture(env_file: Path, output: Path, start: date, end: date,
            symbols: tuple[str, ...], *, transport=None) -> dict:
    if start >= end or end > CUTOFF or not symbols or len(set(symbols)) != len(symbols):
        raise ValueError("Bounded unique development/validation request required")
    if any(symbol not in SECURITIES for symbol in symbols):
        raise ValueError("Unpinned security")
    if output.exists():
        raise ValueError("Immutable action snapshot already exists")
    credentials = MarketDataCredentials(_env_file=env_file)
    headers = {"APCA-API-KEY-ID": credentials.alpaca_api_key.get_secret_value(),
               "APCA-API-SECRET-KEY": credentials.alpaca_api_secret.get_secret_value()}
    params = {"symbols": ",".join(symbols), "start": start.isoformat(),
              "end": end.isoformat(), "data_quality": "all", "limit": 1000}
    payloads, tokens = [], set()
    unattributed = 0
    with httpx.Client(timeout=30, transport=transport) as client:
        while True:
            try:
                response = client.get("https://data.alpaca.markets/v1/corporate-actions",
                                      headers=headers, params=params)
                response.raise_for_status()
                payload = response.json()
            except (httpx.HTTPError, ValueError) as exc:
                raise ValueError("Corporate-action feed unavailable") from exc
            grouped = payload.get("corporate_actions")
            if not isinstance(grouped, dict):
                raise TypeError("Unexpected corporate-action response")
            for rows in grouped.values():
                if not isinstance(rows, list):
                    raise TypeError("Unexpected corporate-action event list")
                for row in rows:
                    if row.get("symbol") not in symbols:
                        unattributed += 1
                    for name in ("ex_date", "process_date", "payable_date", "record_date"):
                        if row.get(name) and date.fromisoformat(row[name]) > CUTOFF:
                            raise ValueError("Reserved 2026 OOS event in response")
            payloads.append(payload)
            token = payload.get("next_page_token")
            if not token:
                break
            if not isinstance(token, str) or token in tokens:
                raise ValueError("Invalid corporate-action pagination")
            tokens.add(token)
            params["page_token"] = token
    acquired = datetime.now(UTC).isoformat()
    raw = json.dumps({"scope": "DEVELOPMENT_AND_VALIDATION_ONLY", "oos_exposed": False,
                      "start": start.isoformat(), "end": end.isoformat(),
                      "symbols": symbols, "retrieved_at": acquired, "pages": payloads},
                     indent=2, default=str).encode()
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_bytes(raw)
    manifest = {"path": output.name, "sha256": hashlib.sha256(raw).hexdigest(),
                "pages": len(payloads), "retrieved_at": acquired,
                "unattributed_rows": unattributed,
                "historical_publication_proven": False, "complete_coverage_proven": False}
    output.with_suffix(output.suffix + ".manifest.json").write_text(
        json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    return manifest


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--env-file", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--start", required=True, type=date.fromisoformat)
    parser.add_argument("--end", required=True, type=date.fromisoformat)
    parser.add_argument("--symbols", required=True)
    args = parser.parse_args()
    result = capture(args.env_file, args.output, args.start, args.end,
                     tuple(args.symbols.split(",")))
    print(f"Action snapshot preserved: {result['pages']} pages; hash {result['sha256']}")


if __name__ == "__main__":
    main()
