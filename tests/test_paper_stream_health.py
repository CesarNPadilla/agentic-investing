from dataclasses import replace

import pytest

from market_data.paper_stream_health import StreamHealth, health_reasons, pong, probe


def ready():
    return StreamHealth(epoch="connection-1", authenticated=True, subscribed=True)


def test_connection_bound_probe_and_deadline():
    state = probe(ready(), epoch="connection-1", token="nonce-1", now=10)
    state = pong(state, epoch="connection-1", token="nonce-1", now=11)
    assert health_reasons(state, now=16) == ()
    assert "STREAM_TRANSPORT_HEALTH_UNVERIFIED" in health_reasons(state, now=16.001)
    assert state.pong_at == 11


@pytest.mark.parametrize(
    "epoch,token,now",
    [
        ("old-connection", "nonce-1", 11),
        ("connection-1", "wrong", 11),
        ("connection-1", "nonce-1", 9),
        ("connection-1", "nonce-1", 15.001),
    ],
)
def test_wrong_or_late_pong_loses_continuity(epoch, token, now):
    state = probe(ready(), epoch="connection-1", token="nonce-1", now=10)
    assert pong(state, epoch=epoch, token=token, now=now).continuity_lost


def test_resume_cannot_clear_loss_and_reconnect_has_no_health():
    state = probe(
        replace(ready(), continuity_lost=True), epoch="connection-1", token="nonce-1", now=10
    )
    state = pong(state, epoch="connection-1", token="nonce-1", now=11)
    assert "STREAM_CONTINUITY_LOST" in health_reasons(state, now=11)
    assert health_reasons(StreamHealth(epoch="connection-2"), now=11)


def test_overlapping_probe_and_invalid_monotonic_time():
    state = probe(ready(), epoch="connection-1", token="nonce-1", now=10)
    assert probe(state, epoch="connection-1", token="nonce-2", now=11).continuity_lost
    with pytest.raises(ValueError):
        health_reasons(state, now=float("nan"))
