"""Bounded read-only IEX status subscription probe. Never orders or credentials output."""

import argparse
import json
import logging
import time
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

from dotenv import dotenv_values
from websockets.exceptions import WebSocketException
from websockets.sync.client import connect

from market_data.paper_status import PaperStatusState, apply_status
from market_data.paper_stream_health import StreamHealth, health_reasons, pong
from market_data.paper_stream_health import probe as health_probe
from strategies.paper_etf_scope import selected_symbol


def probe(
    key, secret, *, connector=connect, monotonic=time.monotonic, monitor_seconds=0, symbol="INTC"
):
    if symbol not in {"SCHB", "INTC"}:
        raise ValueError("Unsupported diagnostic security")
    if type(monitor_seconds) is not int or not 0 <= monitor_seconds <= 60:
        raise ValueError("Bounded monitor duration required")
    result = {
        "authenticated": False,
        "status_subscription_acknowledged": False,
        "initial_status_verified": False,
        "transport_probe_responses": 0,
        "transport_probe_verified": False,
        "monitor_completed": False,
        "status_events_observed": 0,
        "observed_status": "UNKNOWN",
        "execution_available": False,
    }
    logger = logging.getLogger("agentic.paper.stream.probe")
    logger.disabled = True
    try:
        with connector(
            "wss://stream.data.alpaca.markets/v2/iex",
            open_timeout=10,
            close_timeout=2,
            max_size=65536,
            logger=logger,
        ) as stream:

            def receive():
                rows = json.loads(stream.recv(timeout=5))
                if not isinstance(rows, list) or not all(isinstance(x, dict) for x in rows):
                    raise ValueError("Malformed stream response")
                for row in rows:
                    if row.get("T") == "error":
                        result["provider_error_code"] = (
                            row.get("code") if isinstance(row.get("code"), int) else None
                        )
                        raise ValueError("Stream rejected")
                return rows

            receive()
            stream.send(json.dumps({"action": "auth", "key": key, "secret": secret}))
            rows = receive()
            result["authenticated"] = any(
                x.get("T") == "success" and x.get("msg") == "authenticated" for x in rows
            )
            if not result["authenticated"]:
                raise ValueError("Authentication unconfirmed")
            stream.send(json.dumps({"action": "subscribe", "statuses": [symbol]}))
            rows = receive()
            result["status_subscription_acknowledged"] = any(
                x.get("T") == "subscription"
                and isinstance(x.get("statuses"), list)
                and symbol in x["statuses"]
                for x in rows
            )
            result["blockers"] = [
                "INITIAL_STATUS_BOOTSTRAP_UNVERIFIED",
                "CONTINUOUS_STREAM_HEALTH_UNQUALIFIED",
            ]
            if not result["status_subscription_acknowledged"]:
                result["blockers"].append("STATUS_SUBSCRIPTION_UNCONFIRMED")
            else:
                epoch = str(uuid4())
                health = StreamHealth(epoch=epoch, authenticated=True, subscribed=True)
                for _ in range(3):
                    token = str(uuid4())
                    health = health_probe(health, epoch=epoch, token=token, now=monotonic())
                    # ack_on_close defaults false: a closed socket is never a matching pong.
                    response = stream.ping(token)
                    if not response.wait(timeout=5):
                        result["blockers"].append("STREAM_PROBE_DEADLINE_MISSED")
                        break
                    health = pong(health, epoch=epoch, token=token, now=monotonic())
                    if health_reasons(health, now=monotonic()):
                        result["blockers"].append("STREAM_TRANSPORT_HEALTH_UNVERIFIED")
                        break
                    result["transport_probe_responses"] += 1
                result["transport_probe_verified"] = result["transport_probe_responses"] == 3
                if result["transport_probe_verified"] and monitor_seconds:
                    status = PaperStatusState(symbol=symbol, connection_epoch=epoch)
                    deadline = monotonic() + monitor_seconds
                    while monotonic() < deadline:
                        try:
                            raw = stream.recv(timeout=min(1, max(0.001, deadline - monotonic())))
                            rows = json.loads(raw)
                            if not isinstance(rows, list):
                                raise TypeError("Malformed monitor frame")
                            for row in rows:
                                if not isinstance(row, dict) or row.get("T") == "error":
                                    raise ValueError("Monitor source failed")
                                if row.get("T") == "s":
                                    status = apply_status(
                                        status,
                                        row,
                                        connection_epoch=epoch,
                                        received_at=datetime.now(UTC),
                                    )
                                    result["status_events_observed"] += 1
                        except TimeoutError:
                            pass  # Quiet status streams need not emit repeated unchanged status.
                        token = str(uuid4())
                        health = health_probe(health, epoch=epoch, token=token, now=monotonic())
                        if not stream.ping(token).wait(timeout=5):
                            raise TimeoutError("Monitor transport probe failed")
                        health = pong(health, epoch=epoch, token=token, now=monotonic())
                        if health_reasons(health, now=monotonic()):
                            raise ValueError("Monitor continuity lost")
                    result["monitor_completed"] = True
                    result["observed_status"] = status.observed_status
                    result["status_continuity_lost"] = status.continuity_lost
    except (OSError, TimeoutError, ValueError, TypeError, WebSocketException):
        result["blockers"] = ["STATUS_STREAM_PROBE_FAILED"]
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--env-file", type=Path, required=True)
    parser.add_argument("--monitor-seconds", type=int, default=0, choices=range(61))
    args = parser.parse_args()
    values = dotenv_values(args.env_file)
    key, secret = values.get("AIL_ALPACA_API_KEY"), values.get("AIL_ALPACA_API_SECRET")
    if not key or not secret:
        print(json.dumps({"error": "Missing credentials", "execution_available": False}))
        return 1
    result = probe(
        key,
        secret,
        monitor_seconds=args.monitor_seconds,
        symbol=selected_symbol(Path(__file__).resolve().parents[1]),
    )
    print(json.dumps(result, indent=2))
    return 0 if result["authenticated"] and result["status_subscription_acknowledged"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
