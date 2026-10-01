"""Read-only raw-bar snapshot, locked to development/validation through 2025."""

import argparse
import json
from datetime import date
from pathlib import Path

from experiment_lab.alpaca_historical import AlpacaRawPriceProvider
from experiment_lab.historical_fetch import MarketDataCredentials

LATEST_PERMITTED = date(2025, 12, 31)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--env-file", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--symbols", required=True)
    parser.add_argument("--start", type=date.fromisoformat, required=True)
    parser.add_argument("--end", type=date.fromisoformat, required=True)
    parser.add_argument("--feed", choices=("iex", "sip"), default="iex")
    args = parser.parse_args()
    if args.end > LATEST_PERMITTED:
        raise ValueError("Reserved out-of-sample dates may not be fetched")
    if args.output.exists():
        raise ValueError("Raw snapshot is immutable; output already exists")
    settings = MarketDataCredentials(_env_file=args.env_file)
    provider = AlpacaRawPriceProvider(
        settings.alpaca_api_key.get_secret_value(),
        settings.alpaca_api_secret.get_secret_value(), feed=args.feed,
    )
    bars = provider.bars(tuple(args.symbols.split(",")), args.start, args.end)
    args.output.write_text(json.dumps({
        "scope": "DEVELOPMENT_AND_VALIDATION_ONLY", "adjustment_mode": "raw",
        "holdout_exposed": False, "bars": [bar.model_dump(mode="json") for bar in bars],
    }, indent=2) + "\n", encoding="utf-8")
    print(f"Raw development/validation bars written: {len(bars)}")


if __name__ == "__main__":
    main()
