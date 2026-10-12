"""Bounded process-supervised read-only paper event monitor."""

import argparse
import json
from pathlib import Path

from workers.paper_event_process_supervisor import supervise_events


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for field in ("env-file", "ledger-file", "owner-credential-file"):
        parser.add_argument("--" + field, type=Path, required=True)
    parser.add_argument("--seconds", type=int, default=5, choices=range(1, 61))
    args = parser.parse_args()
    result = supervise_events(
        Path(__file__).resolve().parents[1],
        env_file=args.env_file,
        ledger_file=args.ledger_file,
        owner_credential_file=args.owner_credential_file,
        seconds=args.seconds,
    )
    print(json.dumps(result, indent=2))
    return 0 if result.get("monitor_completed") else 1


if __name__ == "__main__":
    raise SystemExit(main())
