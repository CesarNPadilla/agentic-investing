"""Read-only sandbox event diagnostic; signed SDK output is discarded by parent."""

import argparse
import json
import logging
import os
import time
from contextlib import redirect_stderr, redirect_stdout
from datetime import UTC, datetime
from pathlib import Path


def child(env_file, selection_file, report_file, gate):
    # A containment handshake precedes credential access and SDK initialization.
    deadline = time.monotonic() + 5
    while not gate.exists():
        if time.monotonic() >= deadline:
            raise ValueError("Containment handshake absent")
        time.sleep(0.05)
    if gate.read_text() != "CONTAINED_DIAGNOSTIC":
        raise ValueError("Containment handshake invalid")
    logging.disable(logging.CRITICAL)
    os.chdir(env_file.parent)
    from dotenv import dotenv_values
    from webull.core.client import ApiClient
    from webull.core.retry.retry_condition import RetryCondition
    from webull.trade.trade_client import TradeClient
    from webull.trade.trade_events_client import TradeEventsClient

    from integrations.brokers.webull_cash_evidence import WebullCashEvidenceReader

    values = dotenv_values(env_file)
    selection = json.loads(selection_file.read_text())
    key, secret = values["AIL_WEBULL_APP_KEY"], values["AIL_WEBULL_APP_SECRET"]
    api = ApiClient(key, secret, "us")
    api.add_endpoint("us", "api.sandbox.webull.com")
    WebullCashEvidenceReader(TradeClient(api), selection).observe()
    started = time.monotonic()
    evidence = {
        "schema_version": "webull-event-observation-v1",
        "endpoint": "events-api.sandbox.webull.com",
        "selected_account_revalidated": True,
        "started_at_utc": datetime.now(UTC).isoformat(),
        "subscribed": False,
        "heartbeat_count": 0,
        "source_error_count": 0,
        "unclassified_message_count": 0,
        "retry_enabled": False,
        "execution_available": False,
        "trial_started": False,
        "blockers": [
            "EVENT_REPLAY_UNQUALIFIED",
            "EVENT_RUNTIME_INTEGRATION_PENDING",
            "SDK_SUBSCRIPTION_TYPE_UNQUALIFIED",
        ],
    }

    def retain():
        evidence["last_observation_elapsed_seconds"] = round(time.monotonic() - started, 3)
        temporary = report_file.with_suffix(".tmp")
        temporary.write_text(json.dumps(evidence, indent=2) + "\n")
        os.replace(temporary, report_file)

    class NoRetry:
        def should_retry(self, context):
            return RetryCondition.NO_RETRY

    class DiagnosticClient(TradeEventsClient):
        def _easy_handler(self, response):
            # SDK enum: success=0, ping=1, auth/connection/expiry errors=2..4.
            # Other messages remain unclassified; no payload is logged or applied.
            event = response.eventType
            if event == 0:
                evidence["subscribed"] = True
            elif event == 1:
                evidence["heartbeat_count"] += 1
            elif event in (2, 3, 4):
                evidence["source_error_count"] += 1
            else:
                evidence["unclassified_message_count"] += 1
            retain()

    retain()
    try:
        DiagnosticClient(
            key, secret, host=evidence["endpoint"], tls_enable=True, retry_policy=NoRetry()
        ).do_subscribe([selection["account_id"]])
        evidence["stream_ended"] = True
    except Exception:  # noqa: BLE001 -- SDK exception payloads must not escape diagnostic boundary.
        evidence["stream_failed"] = True
    retain()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--env-file", type=Path, required=True)
    parser.add_argument("--selection-file", type=Path, required=True)
    parser.add_argument("--seconds", type=int, default=35)
    parser.add_argument("--child-report", type=Path, help=argparse.SUPPRESS)
    parser.add_argument("--startup-gate", type=Path, help=argparse.SUPPRESS)
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    args.env_file, args.selection_file = args.env_file.resolve(), args.selection_file.resolve()
    try:
        if args.child_report is not None:
            paths = [
                args.env_file,
                args.selection_file,
                args.child_report.resolve(),
                args.startup_gate.resolve(),
            ]
            if any(p.is_relative_to(root) for p in paths):
                raise ValueError("Private paths required")
            with open(os.devnull, "w") as sink, redirect_stdout(sink), redirect_stderr(sink):
                child(*paths)
        else:
            from workers.webull_event_probe import supervise_probe

            print(
                json.dumps(
                    supervise_probe(root, args.env_file, args.selection_file, seconds=args.seconds)
                )
            )
    except Exception:  # noqa: BLE001 -- sanitize private SDK/process failures at CLI boundary.
        # SDK exception text can contain secrets or account identifiers.
        print("Webull diagnostic unavailable; private details suppressed.")
        raise SystemExit(1) from None


if __name__ == "__main__":
    main()
