import json
from threading import Event

from scripts.check_alpaca_trade_updates import probe


class Stream:
    def __init__(self, rows):
        self.rows = iter(rows)
        self.sent = []

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def send(self, payload):
        self.sent.append(json.loads(payload))

    def recv(self, **kwargs):
        try:
            return json.dumps(next(self.rows)).encode()
        except StopIteration:
            raise TimeoutError from None

    def ping(self):
        event = Event()
        event.set()
        return event


AUTH = {"stream": "authorization", "data": {"status": "authorized"}}
LISTEN = {"stream": "listening", "data": {"streams": ["trade_updates"]}}


def test_binary_frames_and_every_event_callback():
    stream = Stream(
        [
            AUTH,
            LISTEN,
            {"stream": "trade_updates", "data": {"event": "partial_fill"}},
            {"stream": "trade_updates", "data": {"event": "canceled"}},
        ]
    )
    ticks = iter(range(100))
    checked = []

    def connector(url, **kwargs):
        assert url == "wss://paper-api.alpaca.markets/stream"
        return stream

    result = probe(
        "private-key",
        "private-secret",
        seconds=10,
        connector=connector,
        monotonic=lambda: next(ticks),
        on_event=checked.append,
    )
    assert result["monitor_completed"] and result["event_checks_completed"] == 2
    assert [row["event"] for row in checked] == ["partial_fill", "canceled"]
    assert [row["action"] for row in stream.sent] == ["auth", "listen"]
    assert "private" not in str(result) and not result["execution_available"]


def test_callback_failure_closes_probe_without_private_detail():
    stream = Stream([AUTH, LISTEN, {"stream": "trade_updates", "data": {"event": "fill"}}])
    ticks = iter(range(100))

    def failed(row):
        raise RuntimeError("private-risk-error")

    result = probe(
        "k",
        "s",
        seconds=10,
        connector=lambda *a, **kw: stream,
        monotonic=lambda: next(ticks),
        on_event=failed,
    )
    assert not result["monitor_completed"] and result["event_checks_completed"] == 0
    assert "private-risk-error" not in str(result)


def test_unauthorized_subscription_blocks():
    stream = Stream([{"stream": "authorization", "data": {"status": "unauthorized"}}])
    result = probe("k", "s", connector=lambda *a, **kw: stream)
    assert not result["authenticated"] and not result["monitor_completed"]


def test_quiet_stream_still_dispatches_timer_callbacks():
    stream = Stream([AUTH, LISTEN])
    ticks = iter(range(100))
    timers = []
    result = probe(
        "k",
        "s",
        seconds=15,
        connector=lambda *a, **kw: stream,
        monotonic=lambda: next(ticks),
        on_timer=lambda: timers.append(True),
    )
    assert result["monitor_completed"]
    assert result["events_received"] == 0
    assert result["timer_callbacks_completed"] == len(timers) and timers
