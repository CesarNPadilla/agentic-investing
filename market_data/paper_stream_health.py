"""Connection-bound transport probe state; never establishes security trading status."""

import math
from dataclasses import dataclass, replace


@dataclass(frozen=True)
class StreamHealth:
    epoch: str
    authenticated: bool = False
    subscribed: bool = False
    probe_token: str | None = None
    sent_at: float | None = None
    pong_at: float | None = None
    continuity_lost: bool = False


def _time(value):
    if not isinstance(value, (int, float)) or not math.isfinite(value) or value < 0:
        raise ValueError("Finite nonnegative monotonic time required")


def probe(state, *, epoch, token, now):
    _time(now)
    if epoch != state.epoch or not token or not state.authenticated or not state.subscribed:
        raise ValueError("Authenticated subscribed connection-bound probe required")
    if state.probe_token is not None or (state.pong_at is not None and now < state.pong_at):
        return replace(state, continuity_lost=True)
    return replace(state, probe_token=token, sent_at=now)


def pong(state, *, epoch, token, now):
    _time(now)
    if (
        epoch != state.epoch
        or token != state.probe_token
        or state.sent_at is None
        or now < state.sent_at
        or now - state.sent_at > 5
    ):
        return replace(state, continuity_lost=True)
    return replace(state, probe_token=None, sent_at=None, pong_at=now)


def health_reasons(state, *, now):
    _time(now)
    reasons = []
    if not state.authenticated or not state.subscribed:
        reasons.append("STREAM_AUTH_SUBSCRIPTION_UNVERIFIED")
    if state.continuity_lost:
        reasons.append("STREAM_CONTINUITY_LOST")
    if state.pong_at is None or now < state.pong_at or now - state.pong_at > 5:
        reasons.append("STREAM_TRANSPORT_HEALTH_UNVERIFIED")
    if state.sent_at is not None and (now < state.sent_at or now - state.sent_at > 5):
        reasons.append("STREAM_PROBE_DEADLINE_MISSED")
    return tuple(reasons)
