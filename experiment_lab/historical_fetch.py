"""Acquire read-only Alpaca daily history; retain unverified-vintage flags."""

import argparse
from datetime import date
from pathlib import Path

from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

from experiment_lab.alpaca_historical import AlpacaHistoricalResearchProvider


class MarketDataCredentials(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="AIL_", extra="ignore")
    alpaca_api_key: SecretStr = SecretStr("")
    alpaca_api_secret: SecretStr = SecretStr("")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--env-file", type=Path,
                        help="External Alpaca settings file; never copied into the artifact")
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--dataset-id", required=True)
    parser.add_argument("--version", default="1")
    parser.add_argument("--symbols", required=True)
    parser.add_argument("--start", type=date.fromisoformat, required=True)
    parser.add_argument("--end", type=date.fromisoformat, required=True)
    parser.add_argument("--feed", choices=("iex", "sip"), default="iex")
    args = parser.parse_args()
    if args.output.exists():
        raise ValueError("Refusing to overwrite an immutable historical export")
    settings = MarketDataCredentials(_env_file=args.env_file if args.env_file else ".env")
    provider = AlpacaHistoricalResearchProvider(
        settings.alpaca_api_key.get_secret_value(),
        settings.alpaca_api_secret.get_secret_value(),
        feed=args.feed, symbols=tuple(s.strip().upper() for s in args.symbols.split(",")
                                     if s.strip()), start=args.start, end=args.end,
    )
    data = provider.load(args.dataset_id, args.version)
    args.output.write_text(data.model_dump_json(indent=2) + "\n", encoding="utf-8")
    print(f"Historical export written: {args.output} (PIT adjustments unverified)")


if __name__ == "__main__":
    main()
