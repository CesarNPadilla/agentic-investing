"""Retain exact broker NY-midnight equity privately; no orders or baseline approximation."""

import argparse
import json
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from dotenv import dotenv_values

from integrations.brokers.alpaca_paper_boundary import AlpacaPaperBoundaryReader
from integrations.brokers.alpaca_paper_read import AlpacaPaperAccountReader
from market_data.base import ProviderUnavailable
from risk.paper_daily_loss import retain_boundary_evidence
from risk.paper_state import PaperState, PaperStateError
from workers.paper_trial_observer import windows_clock


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--env-file", required=True, type=Path)
    parser.add_argument("--ledger-file", required=True, type=Path)
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    if args.ledger_file.resolve().is_relative_to(root):
        parser.error("Private state must be outside repository")
    clock = windows_clock(root)
    if not clock["checks_passed"]:
        print(
            json.dumps(
                {"retained": False, "blockers": clock["blockers"], "execution_available": False}
            )
        )
        return 1
    try:
        values = dotenv_values(args.env_file)
        key, secret = values["AIL_ALPACA_API_KEY"], values["AIL_ALPACA_API_SECRET"]
        account = AlpacaPaperAccountReader(key, secret)
        evidence = AlpacaPaperBoundaryReader(key, secret, account_reader=account).read(
            datetime.now(ZoneInfo("America/New_York")).date()
        )
        retain_boundary_evidence(PaperState(args.ledger_file), evidence)
        print(
            json.dumps(
                {
                    "retained": True,
                    "exact_midnight": True,
                    "source_kind": evidence.source_kind,
                    "account_binding_matched": True,
                    "source_digest": evidence.source_digest,
                    "flow_reconciliation_qualified": False,
                    "execution_available": False,
                }
            )
        )
        return 0
    except (ProviderUnavailable, PaperStateError, KeyError, ValueError, OSError):
        print(
            json.dumps(
                {
                    "retained": False,
                    "blockers": ["BOUNDARY_RETENTION_FAILED"],
                    "execution_available": False,
                }
            )
        )
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
