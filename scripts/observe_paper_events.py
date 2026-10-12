"""Bounded read-only order/fill and timer observation; never starts the trial."""

import argparse
import json
from pathlib import Path

from dotenv import dotenv_values

from integrations.brokers.alpaca_paper_read import AlpacaPaperAccountReader
from risk.paper_state import PaperState, PaperStateError
from scripts.check_alpaca_trade_updates import probe
from strategies.paper_etf_scope import selected_symbol
from workers.paper_connection_journal import PaperConnectionJournal
from workers.paper_event_observer import PaperEventObserver
from workers.paper_trial_observer import build_cycle


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--env-file", type=Path, required=True)
    parser.add_argument("--ledger-file", type=Path, required=True)
    parser.add_argument("--seconds", type=int, default=15, choices=range(1, 61))
    parser.add_argument("--owner-credential-file", type=Path)
    parser.add_argument("--heartbeat-lines", action="store_true")
    parser.add_argument("--startup-gate", type=Path)
    parser.add_argument("--startup-token")
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    if args.startup_gate is not None or args.startup_token is not None:
        from workers.paper_startup_gate import await_startup_gate

        try:
            if args.startup_gate is None or args.startup_token is None:
                raise ValueError("Both startup gate arguments required")
            await_startup_gate(args.startup_gate, args.startup_token, root=root)
        except (OSError, ValueError):
            print(
                json.dumps(
                    {
                        "kind": "failed",
                        "blockers": ["STARTUP_CONTAINMENT_UNVERIFIED"],
                        "execution_available": False,
                        "trial_started": False,
                    }
                ),
                flush=True,
            )
            return 1
    if args.ledger_file.resolve().is_relative_to(root):
        parser.error("Private ledger must be outside repository")
    store = PaperState(args.ledger_file)
    try:
        recovery_credential = None
        if args.owner_credential_file:
            from fido2.utils import websafe_decode
            from fido2.webauthn import AttestedCredentialData

            if args.owner_credential_file.resolve().is_relative_to(root):
                raise ValueError("Owner credential must be outside repository")
            recovery_credential = AttestedCredentialData(
                websafe_decode(
                    json.loads(args.owner_credential_file.read_text(encoding="utf-8"))[
                        "credential_data"
                    ]
                )
            )
        values = dotenv_values(args.env_file)
        key, secret = values["AIL_ALPACA_API_KEY"], values["AIL_ALPACA_API_SECRET"]
        account_reader = AlpacaPaperAccountReader(key, secret)
        observer = PaperEventObserver(
            store,
            build_cycle(root, values, args.ledger_file),
            account_binding=account_reader.observe().account_binding_sha256,
            symbol=selected_symbol(root),
            recovery_credential=recovery_credential,
        )
        observer.check("STARTUP")

        def heartbeat():
            if args.heartbeat_lines:
                report = observer.reports[-1]
                print(
                    json.dumps(
                        {
                            "kind": "check",
                            "sequence": len(observer.reports),
                            "account_observed": report.get("account_observed"),
                            "blockers": report["blockers"],
                            "execution_available": False,
                            "trial_started": False,
                        }
                    ),
                    flush=True,
                )

        def event(payload):
            observer.on_event(payload)
            heartbeat()

        def timer():
            observer.on_timer()
            heartbeat()

        heartbeat()
        connection = PaperConnectionJournal(store)

        def connected():
            report = observer.check("CONNECTION_RECONCILIATION")
            connection.connected_after_check(report)
            heartbeat()

        result = probe(
            key,
            secret,
            seconds=args.seconds,
            on_event=event,
            on_timer=timer,
            on_connected=connected,
        )
        if account_reader.observe().account_binding_sha256 != store.read()["binding"]:
            raise PaperStateError("Account changed during event observation")
        if not result["monitor_completed"]:
            store.latch("PAPER_EVENT_STREAM_FAILED")
        connection.finish(completed=result["monitor_completed"])
        print(
            json.dumps(
                {
                    "kind": "complete",
                    "stream": result,
                    "diagnostic_cycles": len(observer.reports),
                    "latest_diagnostic": observer.reports[-1],
                    "execution_available": False,
                    "trial_started": False,
                },
                indent=None if args.heartbeat_lines else 2,
            ),
            flush=True,
        )
        return 0 if result["monitor_completed"] else 1
    except (RuntimeError, ValueError, TypeError, KeyError, OSError):
        print(
            json.dumps(
                {
                    "kind": "failed",
                    "blockers": ["PAPER_EVENT_OBSERVATION_FAILED"],
                    "execution_available": False,
                    "trial_started": False,
                }
            )
        )
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
