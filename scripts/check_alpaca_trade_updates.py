"""Bounded read-only paper order/fill stream probe; no submissions or admission."""

import argparse
import json
import logging
import time
from pathlib import Path

from dotenv import dotenv_values
from websockets.exceptions import WebSocketException
from websockets.sync.client import connect


def probe(
    key,
    secret,
    *,
    seconds=10,
    connector=connect,
    monotonic=time.monotonic,
    on_event=None,
    on_timer=None,
    timer_seconds=1,
    on_connected=None,
):
    if type(seconds) is not int or not 1 <= seconds <= 60:
        raise ValueError("Bounded trade-update duration required")
    if type(timer_seconds) is not int or not 1 <= timer_seconds <= 5:
        raise ValueError("Timer interval must be one to five seconds")
    result = {
        "authenticated": False,
        "subscribed": False,
        "monitor_completed": False,
        "events_received": 0,
        "event_checks_completed": 0,
        "timer_callbacks_completed": 0,
        "execution_available": False,
        "trial_started": False,
    }
    logger = logging.getLogger("agentic.paper.trade-update.probe")
    logger.disabled = True
    try:
        with connector(
            "wss://paper-api.alpaca.markets/stream",
            open_timeout=10,
            close_timeout=2,
            max_size=65536,
            logger=logger,
        ) as stream:

            def receive(timeout):
                row = json.loads(stream.recv(timeout=timeout))
                if not isinstance(row, dict) or not isinstance(row.get("data"), dict):
                    raise TypeError("Malformed trade-update frame")
                return row

            stream.send(json.dumps({"action": "auth", "key": key, "secret": secret}))
            row = receive(5)
            result["authenticated"] = (
                row.get("stream") == "authorization" and row["data"].get("status") == "authorized"
            )
            if not result["authenticated"]:
                raise ValueError("Paper stream authentication failed")
            stream.send(json.dumps({"action": "listen", "data": {"streams": ["trade_updates"]}}))
            row = receive(5)
            result["subscribed"] = row.get("stream") == "listening" and row["data"].get(
                "streams"
            ) == ["trade_updates"]
            if not result["subscribed"]:
                raise ValueError("Paper stream subscription failed")
            if on_connected is not None:
                on_connected()
            last_timer = monotonic()
            deadline = last_timer + seconds
            while monotonic() < deadline:
                try:
                    row = receive(min(1, max(0.001, deadline - monotonic())))
                except TimeoutError:
                    row = None
                if row is not None:
                    if row.get("stream") != "trade_updates":
                        raise ValueError("Unexpected paper stream message")
                    result["events_received"] += 1
                    if on_event is not None:
                        on_event(row["data"])
                        result["event_checks_completed"] += 1
                # A quiet event stream is checked with actual matching websocket pongs.
                if not stream.ping().wait(timeout=5):
                    raise TimeoutError("Paper stream transport deadline missed")
                instant = monotonic()
                if instant < last_timer:
                    raise ValueError("Monotonic clock regressed")
                if on_timer is not None and instant - last_timer >= timer_seconds:
                    on_timer()
                    result["timer_callbacks_completed"] += 1
                    last_timer = monotonic()
            result["monitor_completed"] = True
            result["blockers"] = [
                "TRADE_EVENT_RUNTIME_UNQUALIFIED",
                "PERSISTENT_SUPERVISION_UNQUALIFIED",
            ]
    except (OSError, TimeoutError, ValueError, TypeError, RuntimeError, WebSocketException):
        result["blockers"] = ["PAPER_TRADE_UPDATE_PROBE_FAILED"]
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--env-file", type=Path, required=True)
    parser.add_argument("--seconds", type=int, default=10, choices=range(1, 61))
    args = parser.parse_args()
    values = dotenv_values(args.env_file)
    key, secret = values.get("AIL_ALPACA_API_KEY"), values.get("AIL_ALPACA_API_SECRET")
    if not key or not secret:
        print(json.dumps({"error": "Missing credentials", "execution_available": False}))
        return 1
    result = probe(key, secret, seconds=args.seconds)
    print(json.dumps(result, indent=2))
    return 0 if result["monitor_completed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
