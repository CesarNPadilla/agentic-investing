"""Paper status-stream diagnostics; no entitlement/bootstrap or order permission."""

from datetime import datetime
from typing import Literal

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field

from market_data.models import Symbol


class StatusEvent(BaseModel):
    model_config = ConfigDict(frozen=True, extra="ignore")
    T: Literal["s"]
    S: Symbol
    sc: str = Field(min_length=1)
    t: AwareDatetime
    z: Literal["A", "B", "C", "O"]


class PaperStatusState(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    symbol: Symbol
    connection_epoch: str = Field(min_length=1)
    observed_status: Literal["UNKNOWN", "HALTED", "RESUME_OBSERVED"] = "UNKNOWN"
    last_event_at: AwareDatetime | None = None
    last_received_at: AwareDatetime | None = None
    last_code: str | None = None
    last_tape: str | None = None
    continuity_lost: bool = False
    execution_available: Literal[False] = False


def apply_status(state, payload, *, connection_epoch, received_at):
    if received_at.tzinfo is None or received_at.utcoffset() is None:
        raise ValueError("Aware receipt required")
    if state.connection_epoch != connection_epoch:
        raise ValueError("Stale connection epoch")
    event = StatusEvent.model_validate(payload)
    if event.S != state.symbol or event.t > received_at:
        raise ValueError("Symbol or future status mismatch")
    if (state.last_event_at is not None and event.t < state.last_event_at) or (
        state.last_received_at is not None and received_at < state.last_received_at
    ):
        return state.model_copy(update={"observed_status": "UNKNOWN", "continuity_lost": True})
    if state.last_event_at == event.t:
        if state.last_code == event.sc and state.last_tape == event.z:
            return state  # Exact semantic replay does not refresh continuity evidence.
        return state.model_copy(update={"observed_status": "UNKNOWN", "continuity_lost": True})
    if event.z in {"A", "B"}:
        status = (
            "HALTED"
            if event.sc in {"2", "F"}
            else "RESUME_OBSERVED"
            if event.sc == "3"
            else "UNKNOWN"
        )
    else:
        status = (
            "HALTED"
            if event.sc in {"H", "P"}
            else "RESUME_OBSERVED"
            if event.sc == "T"
            else "UNKNOWN"
        )
    return state.model_copy(
        update={
            "observed_status": status,
            "last_event_at": event.t,
            "last_received_at": received_at,
            "last_code": event.sc,
            "last_tape": event.z,
        }
    )


def disconnect(state, *, new_epoch):
    return PaperStatusState(symbol=state.symbol, connection_epoch=new_epoch, continuity_lost=True)


def status_reasons(state, *, now: datetime):
    if now.tzinfo is None or now.utcoffset() is None:
        raise ValueError("Aware evaluation time required")
    reasons = ["STATUS_SOURCE_BOOTSTRAP_UNQUALIFIED", "STATUS_STREAM_HEALTH_UNQUALIFIED"]
    if state.continuity_lost:
        reasons.append("STATUS_CONTINUITY_LOST")
    if state.observed_status != "RESUME_OBSERVED":
        reasons.append("STATUS_NOT_TRADING")
    if state.last_received_at is None or state.last_received_at > now:
        reasons.append("STATUS_RECEIPT_UNVERIFIED")
    return tuple(reasons)
