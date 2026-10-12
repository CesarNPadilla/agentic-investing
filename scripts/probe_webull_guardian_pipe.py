"""One synthetic guardian-server/owner-client request; no journal or real reference."""

import argparse
import json
import os
from datetime import UTC, datetime
from pathlib import Path
from uuid import UUID

from security.windows_guardian_request_pipe import GuardianRequestPipe


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--guardian-sid", required=True)
    parser.add_argument("--owner-sid", required=True)
    parser.add_argument("--probe-id", required=True)
    args = parser.parse_args()
    identifier = UUID(args.probe_id)
    if identifier.version != 4 or str(identifier) != args.probe_id:
        raise ValueError("Canonical fixture identifier required")
    root = Path(r"C:\ProgramData\AgenticInvestingGuardian")

    class DummyReference:
        def handle(self, raw, *, now):
            expected = json.dumps({"schema_version": "guardian-pipe-dummy-v1", "id": args.probe_id})
            if raw != expected.encode():
                raise ValueError("Exact synthetic request required")
            return {"synthetic_request_only": True, "execution_available": False}

    pipe = GuardianRequestPipe(guardian_sid=args.guardian_sid, owner_sid=args.owner_sid)
    try:
        with (root / "Logs" / f"guardian-pipe-ready-{args.probe_id}.json").open("x") as stream:
            json.dump({"pipe_name": pipe.name}, stream)
            stream.flush()
            os.fsync(stream.fileno())
        result = pipe.register_one(DummyReference())
        result.update(
            schema_version="guardian-native-pipe-fixture-v1",
            observed_at_utc=datetime.now(UTC).isoformat(),
            probe_id=args.probe_id,
            guardian_process_identity_verified=True,
            reset_performed=False,
            trial_started=False,
        )
        with (root / "Receipts" / f"guardian-pipe-result-{args.probe_id}.json").open("x") as stream:
            json.dump(result, stream)
            stream.flush()
            os.fsync(stream.fileno())
    finally:
        pipe.close()


if __name__ == "__main__":
    main()
