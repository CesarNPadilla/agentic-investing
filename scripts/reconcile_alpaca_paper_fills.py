"""Single paper activity import into private durable trade ledger; no broker orders."""

import argparse
import json
from datetime import UTC, datetime, timedelta
from pathlib import Path

from dotenv import dotenv_values

from integrations.brokers.alpaca_paper_activities import AlpacaPaperActivityReader
from integrations.brokers.alpaca_paper_read import AlpacaPaperAccountReader
from portfolio.paper_fill_ledger import PaperFillLedger


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--env-file", type=Path, required=True)
    parser.add_argument("--ledger-file", type=Path, required=True)
    parser.add_argument("--initialize", action="store_true")
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    if args.ledger_file.resolve().is_relative_to(root):
        parser.error("Private ledger must remain outside repository")
    try:
        values = dotenv_values(args.env_file)
        key, secret = values["AIL_ALPACA_API_KEY"], values["AIL_ALPACA_API_SECRET"]
        observation = AlpacaPaperAccountReader(key, secret).observe()
        if not observation.bracket_stable or not observation.account_unblocked:
            raise ValueError("Account observation blocked")
        ledger = (
            PaperFillLedger.initialize(args.ledger_file, observation)
            if args.initialize
            else PaperFillLedger(args.ledger_file)
        )
        # Overlap prior acquisition to pick up late-published fills; IDs prevent double effects.
        after = datetime.fromisoformat(ledger.read()["acquisition_cutoff"]) - timedelta(days=1)
        batch = AlpacaPaperActivityReader(key, secret).read(after=after, until=datetime.now(UTC))
        report = ledger.import_batch(batch, account_binding=observation.account_binding_sha256)
        print(json.dumps(report, indent=2))
        return 0
    except (RuntimeError, ValueError, OSError, KeyError, TypeError):
        print(
            json.dumps(
                {
                    "error": "Paper ledger import unavailable or invalid; details withheld",
                    "execution_available": False,
                }
            )
        )
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
