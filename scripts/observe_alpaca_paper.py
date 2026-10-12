"""Single read-only paper control cycle, not a broker execution daemon."""

import argparse
import json
from datetime import UTC, datetime
from pathlib import Path

from dotenv import dotenv_values

from integrations.brokers.alpaca_paper_read import AlpacaPaperAccountReader
from market_data.alpaca_evidence import AlpacaPaperQuoteReader
from market_data.nyse_calendar import NysePublishedCalendar
from risk.paper_state import PaperState


def cycle(account_reader, quote_reader, calendar, store, *, now, symbol="INTC"):
    try:
        account = account_reader.observe()
        quote = quote_reader.read(symbol)
        instant = now()
        reasons = (
            set(account.reasons(instant))
            | set(quote.blockers(instant))
            | set(calendar.schedule_reasons(instant))
        )
        reasons.update(
            ("CLOCK_SYNC_UNVERIFIED", "FILL_RECONCILIATION_PENDING", "RESET_AUTHENTICATION_PENDING")
        )
        store.record_observation(account, sorted(reasons))
        state = store.read()
        return {
            "account_observed": True,
            "bracket_stable": account.bracket_stable,
            "empty_inventory": account.empty_inventory,
            "quote_observed": True,
            "blockers": sorted(reasons),
            "latched": state["latched"],
            "execution_available": False,
            "month_trial_started": False,
        }
    except (RuntimeError, ValueError, OSError, TypeError):
        # All failed cycles block; do not expose provider errors or account data.
        try:
            store.latch("OBSERVATION_CYCLE_FAILED")
        except (RuntimeError, ValueError, OSError, TypeError):
            return {
                "blockers": ["PERSISTENCE_UNAVAILABLE"],
                "latched": True,
                "execution_available": False,
                "month_trial_started": False,
            }
        return {
            "blockers": ["OBSERVATION_OR_PERSISTENCE_FAILED"],
            "latched": True,
            "execution_available": False,
            "month_trial_started": False,
        }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--env-file", type=Path, required=True)
    parser.add_argument("--state-file", type=Path, required=True)
    parser.add_argument("--initialize", action="store_true")
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    if args.state_file.resolve().is_relative_to(root):
        parser.error("Private paper state must remain outside the repository")
    values = dotenv_values(args.env_file)
    account = AlpacaPaperAccountReader(
        values.get("AIL_ALPACA_API_KEY"), values.get("AIL_ALPACA_API_SECRET")
    )
    quote = AlpacaPaperQuoteReader(values["AIL_ALPACA_API_KEY"], values["AIL_ALPACA_API_SECRET"])
    store = PaperState(args.state_file)
    if args.initialize:
        binding = account.observe().account_binding_sha256
        store = PaperState.initialize(args.state_file, account_binding=binding)
    report = cycle(
        account,
        quote,
        NysePublishedCalendar(root / "conf/nyse-calendar-2026.json"),
        store,
        now=lambda: datetime.now(UTC),
    )
    print(json.dumps(report, indent=2))
    return 0 if report.get("account_observed") else 1


if __name__ == "__main__":
    raise SystemExit(main())
