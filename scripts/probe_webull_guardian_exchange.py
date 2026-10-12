"""Synthetic cross-account reply fixture; no journal, credential or real reference."""

import argparse
import ctypes
import json
import os
import sys
from ctypes import wintypes
from pathlib import Path
from uuid import UUID

# This file and two transport modules must be copied to an administrator-protected
# new fixture directory before execution with the pinned embedded interpreter.
sys.path.insert(0, str(Path(__file__).resolve().parent))

from security.windows_guardian_exchange_client import GuardianExchangeClient
from security.windows_guardian_exchange_pipe import GuardianExchangePipe


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("mode", choices=["server", "client"])
    parser.add_argument("--guardian-sid", required=True)
    parser.add_argument("--owner-sid", required=True)
    parser.add_argument("--id", required=True)
    parser.add_argument("--standard-owner", action="store_true")
    args = parser.parse_args()
    if str(UUID(args.id)) != args.id or UUID(args.id).version != 4:
        raise ValueError("Canonical fixture ID required")
    root = Path(r"C:\ProgramData\AgenticInvestingGuardian")
    ready = root / "Logs" / f"exchange-ready-{args.id}.json"
    receipt = root / "Receipts" / f"exchange-result-{args.id}.json"
    raw = json.dumps({"synthetic_exchange_fixture": args.id}).encode()
    if args.mode == "server":

        class Dummy:
            def handle(self, value, *, now):
                if value != raw:
                    raise ValueError("Exact synthetic frame required")
                return {
                    "synthetic_request_only": True,
                    "execution_available": False,
                    "reset_authorized": False,
                    "trial_started": False,
                }

        pipe = GuardianExchangePipe(guardian_sid=args.guardian_sid, owner_sid=args.owner_sid)
        try:
            with ready.open("x", encoding="utf-8") as stream:
                json.dump({"pipe_name": pipe.name}, stream)
                stream.flush()
                os.fsync(stream.fileno())
            result = pipe.register_one(Dummy())
            with receipt.open("x", encoding="utf-8") as stream:
                json.dump(
                    result | {"probe_id": args.id, "guardian_reply_receipt_verified": True}, stream
                )
                stream.flush()
                os.fsync(stream.fileno())
        finally:
            pipe.close()
    else:
        client = GuardianExchangeClient(
            name=json.loads(ready.read_text(encoding="utf-8"))["pipe_name"],
            guardian_sid=args.guardian_sid,
        )
        if client.api.read_process_identity() != args.owner_sid:
            raise PermissionError("Configured owner process required")
        if args.standard_owner:
            token, elevation, used = wintypes.HANDLE(), wintypes.DWORD(), wintypes.DWORD()
            api = client.api
            if not api.security.OpenProcessToken(
                api.kernel.GetCurrentProcess(), 8, ctypes.byref(token)
            ):
                raise OSError("Standard owner token unavailable")
            try:
                if (
                    not api.security.GetTokenInformation(
                        token, 20, ctypes.byref(elevation), 4, ctypes.byref(used)
                    )
                    or elevation.value
                ):
                    raise PermissionError("Standard owner process required")
            finally:
                api.kernel.CloseHandle(token)
        result = client.exchange(raw)
        if result != {
            "synthetic_request_only": True,
            "execution_available": False,
            "reset_authorized": False,
            "trial_started": False,
            "owner_pipe_identity_observed": True,
        }:
            raise ValueError("Unexpected synthetic reply")
        print("AUTHENTICATED_GUARDIAN_REPLY_RECEIVED_SYNTHETIC_ONLY")


if __name__ == "__main__":
    main()
