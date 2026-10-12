import json
from threading import Event

from scripts.check_alpaca_status_stream import probe


class Stream:
    def __init__(self, rows):
        self.rows = iter(rows)
        self.sent = []

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def recv(self, **kwargs):
        return json.dumps(next(self.rows))

    def send(self, value):
        self.sent.append(json.loads(value))

    def ping(self, token):
        event = Event()
        event.set()
        return event


def test_auth_subscription_probe_never_claims_initial_active_status():
    stream = Stream(
        [
            [{"T": "success", "msg": "connected"}],
            [{"T": "success", "msg": "authenticated"}],
            [{"T": "subscription", "statuses": ["INTC"]}],
        ]
    )

    def connector(url, **kwargs):
        assert url == "wss://stream.data.alpaca.markets/v2/iex"
        return stream

    result = probe("private-key", "private-secret", connector=connector)
    assert result["authenticated"] and result["status_subscription_acknowledged"]
    assert not result["initial_status_verified"] and not result["execution_available"]
    assert result["transport_probe_verified"] and result["transport_probe_responses"] == 3
    assert "private" not in str(result)
    assert [x["action"] for x in stream.sent] == ["auth", "subscribe"]


def test_entitlement_error_is_sanitized():
    stream = Stream(
        [
            [{"T": "success", "msg": "connected"}],
            [{"T": "error", "code": 409, "msg": "private-details"}],
        ]
    )
    result = probe("k", "s", connector=lambda *args, **kwargs: stream)
    assert not result["authenticated"] and result["provider_error_code"] == 409
    assert "private-details" not in str(result)


def test_missing_pong_blocks_without_claiming_continuous_health():
    class MissingPong:
        def wait(self, *, timeout):
            assert timeout == 5
            return False

    stream = Stream(
        [
            [{"T": "success", "msg": "connected"}],
            [{"T": "success", "msg": "authenticated"}],
            [{"T": "subscription", "statuses": ["INTC"]}],
        ]
    )
    stream.ping = lambda _: MissingPong()
    result = probe("k", "s", connector=lambda *args, **kwargs: stream)
    assert not result["transport_probe_verified"]
    assert "STREAM_PROBE_DEADLINE_MISSED" in result["blockers"]
    assert "CONTINUOUS_STREAM_HEALTH_UNQUALIFIED" in result["blockers"]


def test_bounded_monitor_does_not_infer_trading_from_quiet_stream():
    class Quiet(Stream):
        def recv(self, **kwargs):
            try:
                return super().recv(**kwargs)
            except StopIteration:
                raise TimeoutError from None

    stream = Quiet(
        [
            [{"T": "success", "msg": "connected"}],
            [{"T": "success", "msg": "authenticated"}],
            [{"T": "subscription", "statuses": ["INTC"]}],
        ]
    )
    ticks = iter(range(100))
    result = probe(
        "k",
        "s",
        connector=lambda *args, **kwargs: stream,
        monotonic=lambda: next(ticks),
        monitor_seconds=10,
    )
    assert result["monitor_completed"] and result["observed_status"] == "UNKNOWN"
    assert not result["initial_status_verified"] and not result["execution_available"]
