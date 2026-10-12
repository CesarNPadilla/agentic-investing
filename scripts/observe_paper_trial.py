"""Run bounded integrated read-only paper observer cycles; never starts a trading trial."""

import argparse
import json
import time
from pathlib import Path

from dotenv import dotenv_values

from portfolio.paper_fill_ledger import PaperFillLedger
from workers.paper_observation_deadline import bounded_observation
from workers.paper_trial_observer import build_cycle


def run_cycles(
    cycle,
    *,
    cycles,
    interval_seconds,
    monotonic=time.monotonic,
    sleep=time.sleep,
    deadline_latch=None,
    deadline_seconds=5,
):
    if type(cycles) is not int or not 1 <= cycles <= 1000 or not 5 <= interval_seconds <= 60:
        raise ValueError("Bounded observer configuration required")
    reports = []
    for index in range(cycles):
        started = monotonic()
        report = (
            bounded_observation(cycle, timeout_seconds=deadline_seconds, on_timeout=deadline_latch)
            if deadline_latch is not None
            else cycle()
        )
        duration = monotonic() - started
        if duration < 0 or duration > interval_seconds:
            report = dict(
                report, blockers=sorted(set(report["blockers"]) | {"OBSERVER_DEADLINE_MISSED"})
            )
        if report.get("active_scope") and interval_seconds > 5:
            report = dict(
                report, blockers=sorted(set(report["blockers"]) | {"ACTIVE_SCOPE_TIMER_TOO_SLOW"})
            )
        reports.append(report)
        if "OBSERVER_DEADLINE_MISSED" in report["blockers"]:
            # Never dispatch another read concurrently with an abandoned reader.
            break
        if index + 1 < cycles:
            sleep(max(0, interval_seconds - duration))
    return reports


def run_guarded_cycles(cycle, store, *, cycles, interval_seconds, deadline_seconds=5):
    if "OBSERVER_DEADLINE_MISSED" in store.read()["latch_reasons"]:
        return [
            {
                "blockers": ["SERVICE_RECOVERY_REQUIRED"],
                "execution_available": False,
                "trial_started": False,
            }
        ]
    return run_cycles(
        cycle,
        cycles=cycles,
        interval_seconds=interval_seconds,
        deadline_latch=store.latch,
        deadline_seconds=deadline_seconds,
    )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--env-file", required=True, type=Path)
    parser.add_argument("--ledger-file", required=True, type=Path)
    parser.add_argument("--cycles", type=int, default=1)
    parser.add_argument("--interval-seconds", type=int, default=5)
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    if args.ledger_file.resolve().is_relative_to(root):
        parser.error("Private ledger must be outside repository")
    store = PaperFillLedger(args.ledger_file).store
    reports = run_guarded_cycles(
        build_cycle(root, dotenv_values(args.env_file), args.ledger_file),
        store,
        cycles=args.cycles,
        interval_seconds=args.interval_seconds,
    )
    print(json.dumps(reports, indent=2))
    return 0 if all(r.get("account_observed") for r in reports) else 1


if __name__ == "__main__":
    raise SystemExit(main())
