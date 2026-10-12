"""Owner-run synthetic native pipe fixture, never a deployed execution controller."""

import argparse
import json
import os
import time
from datetime import UTC, datetime
from pathlib import Path

from security.webull_request_journal import RequestJournal
from security.windows_local_request_pipe import LocalRequestPipe
from security.windows_pipe_identity import NativePipeIdentity


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--runtime-sid", required=True)
    for name in ("ready-file", "report-file", "journal-file", "startup-gate"):
        parser.add_argument("--" + name, required=True, type=Path)
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    paths = [args.ready_file, args.report_file, args.journal_file, args.startup_gate]
    if (
        any(p.resolve().is_relative_to(root) for p in paths)
        or len({p.resolve() for p in paths}) != 4
    ):
        parser.error("Distinct private fixture paths outside repository required")
    if any(p.exists() for p in paths):
        parser.error("New exclusive fixture paths required")
    pipe = None
    try:
        owner = NativePipeIdentity().read_process_identity()
        journal = RequestJournal.initialize(args.journal_file, "a" * 64, state_digest="b" * 64)
        pipe = LocalRequestPipe(owner_sid=owner, runtime_sid=args.runtime_sid)
        temporary_ready = args.ready_file.with_suffix(".tmp")
        with temporary_ready.open("x", encoding="utf-8") as ready:
            json.dump(
                {
                    "schema_version": "native-pipe-fixture-ready-v1",
                    "pipe_name": pipe.name,
                    "execution_available": False,
                },
                ready,
            )
            ready.flush()
            os.fsync(ready.fileno())
        # Exclusive atomic publication: observers cannot see partially written JSON.
        os.link(temporary_ready, args.ready_file)
        temporary_ready.unlink()
        deadline = time.monotonic() + 15
        while not args.startup_gate.exists():
            if time.monotonic() >= deadline:
                raise TimeoutError("Owner fixture startup gate absent")
            time.sleep(0.05)
        if args.startup_gate.read_text(encoding="utf-8-sig") != "OWNER_NATIVE_FIXTURE_READY":
            raise ValueError("Owner fixture gate invalid")
        receipt = pipe.register_one(journal)
        if receipt["observed_caller_role"] != "RUNTIME":
            raise ValueError("Runtime identity required for this fixture")
        report = {
            "schema_version": "runtime-native-pipe-fixture-v1",
            "observed_at_utc": datetime.now(UTC).isoformat(),
            "registration": receipt,
            "journal": journal.verify(),
            "scope": "SYNTHETIC_NATIVE_OWNER_RUNTIME_PIPE_ONLY",
            "remote_host_denial_tested": False,
            "service_deployed": False,
            "owner_approval_verified": False,
            "reset_performed": False,
            "execution_available": False,
            "trial_started": False,
        }
        with args.report_file.open("x", encoding="utf-8") as result:
            json.dump(report, result, indent=2)
    finally:
        if pipe is not None:
            pipe.close()


if __name__ == "__main__":
    main()
