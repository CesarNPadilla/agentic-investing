"""Run a bounded supervised read-only observation batch; no orders or trial launch."""

import argparse
import json
from pathlib import Path

from workers.paper_process_supervisor import run_supervised_batch


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--env-file", required=True, type=Path)
    parser.add_argument("--ledger-file", required=True, type=Path)
    parser.add_argument("--cycles", type=int, default=3, choices=range(1, 13))
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    if args.ledger_file.resolve().is_relative_to(root):
        parser.error("Private state must be outside repository")
    try:
        report = run_supervised_batch(
            root, env_file=args.env_file, ledger_file=args.ledger_file, cycles=args.cycles
        )
        print(json.dumps(report, indent=2))
        return 0 if report.get("batch_completed") else 1
    except (RuntimeError, ValueError, TypeError, OSError):
        print(
            json.dumps(
                {
                    "blockers": ["READONLY_SUPERVISION_FAILED"],
                    "execution_available": False,
                    "trial_started": False,
                }
            )
        )
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
