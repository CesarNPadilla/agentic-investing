"""Windowed read-only observation service; fixed paper sources, no order methods."""

import argparse
import json
import os
from datetime import UTC, datetime, timedelta
from pathlib import Path

from market_data.nyse_calendar import NY, NysePublishedCalendar
from risk.paper_state import PaperState
from workers.paper_event_process_supervisor import supervise_events
from workers.paper_readonly_service import run_service


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for field in ("env-file", "ledger-file", "owner-credential-file", "stop-file", "report-file"):
        parser.add_argument("--" + field, type=Path, required=True)
    parser.add_argument("--window-seconds", type=int, default=60, choices=range(5, 61))
    parser.add_argument("--max-windows", type=int, default=390, choices=range(1, 391))
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    try:
        private = [
            args.env_file,
            args.ledger_file,
            args.owner_credential_file,
            args.stop_file,
            args.report_file,
        ]
        if any(path.resolve().is_relative_to(root) for path in private):
            raise ValueError("Private service inputs must remain outside repository")
        calendar = NysePublishedCalendar(root / "conf/nyse-calendar-2026.json")

        def regular_session():
            instant = datetime.now(UTC)
            session = calendar.session(instant.astimezone(NY).date())
            return bool(
                session
                and session.opens_at <= instant
                and instant + timedelta(seconds=args.window_seconds + 15) < session.closes_at
            )

        def report_sink(row):
            args.report_file.parent.mkdir(parents=True, exist_ok=True)
            with args.report_file.open("a", encoding="utf-8") as handle:
                handle.write(json.dumps(row) + "\n")
                handle.flush()
                os.fsync(handle.fileno())

        result = run_service(
            PaperState(args.ledger_file),
            lambda: supervise_events(
                root,
                env_file=args.env_file,
                ledger_file=args.ledger_file,
                owner_credential_file=args.owner_credential_file,
                seconds=args.window_seconds,
            ),
            regular_session=regular_session,
            stop_requested=args.stop_file.exists,
            max_windows=args.max_windows,
            report_sink=report_sink,
        )
        report_sink(result)
        return (
            0
            if result["status"] in {"COMPLETE", "STOPPED", "STOP_REQUESTED", "SESSION_CLOSED"}
            else 1
        )
    except (RuntimeError, ValueError, TypeError, KeyError, OSError):
        # A windowed background app never prints private provider errors.
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
