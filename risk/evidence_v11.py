"""Strict synthetic quote/snapshot/session evidence and review bindings."""
import hashlib
from datetime import date, datetime, time
from typing import Literal
from zoneinfo import ZoneInfo

from pydantic import BaseModel, ConfigDict, Field, model_validator

from risk.sleeve_v11 import Positive

Digest = str
NY = ZoneInfo("America/New_York")


class SyntheticEvidence(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    evidence_class: Literal["SYNTHETIC_ONLY"] = "SYNTHETIC_ONLY"
    symbol: str = Field(pattern=r"^[A-Z][A-Z0-9.]{0,9}$")
    quote_source: str = Field(min_length=1)
    quote_symbol: str = Field(pattern=r"^[A-Z][A-Z0-9.]{0,9}$")
    quote_currency: Literal["USD"] = "USD"
    quote_status: Literal["ACTIVE", "HALTED", "UNKNOWN"] = "UNKNOWN"
    bid: Positive | None = None
    ask: Positive | None = None
    quote_event_time: datetime | None = None
    quote_received_time: datetime | None = None
    snapshot_source: str = Field(min_length=1)
    snapshot_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    snapshot_cutoff: datetime | None = None
    snapshot_complete: bool = False
    snapshot_reconciled: bool = False
    policy_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    calendar_source: str = Field(min_length=1)
    calendar_version: str = Field(min_length=1)
    session_date: date
    session_open: datetime | None = None
    session_close: datetime | None = None
    calendar_verified: bool = False
    broker_regular_session_supported: bool = False
    clock_synchronized: bool = False

    @model_validator(mode="after")
    def timestamps(self):
        for value in (self.quote_event_time, self.quote_received_time, self.snapshot_cutoff,
                      self.session_open, self.session_close):
            if value is not None and (value.tzinfo is None or value.utcoffset() is None):
                raise ValueError("Aware timestamps required")
        if (self.session_open is None) != (self.session_close is None):
            raise ValueError("Closed session has no open/close timestamps")
        if self.session_open is not None:
            start, end = self.session_open.astimezone(NY), self.session_close.astimezone(NY)
            if (start.date() != self.session_date or end.date() != self.session_date
                    or start.time() != time(9, 30) or end.time() > time(16)
                    or start >= end):
                raise ValueError("Invalid regular-session fixture")
        return self

    def digest(self):
        return hashlib.sha256(self.model_dump_json().encode()).hexdigest()


class SyntheticReviewBinding(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    evidence_class: Literal["SYNTHETIC_ONLY"] = "SYNTHETIC_ONLY"
    evidence_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    proposal_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    risk_evaluated_at: datetime

    @model_validator(mode="after")
    def aware(self):
        if self.risk_evaluated_at.tzinfo is None or self.risk_evaluated_at.utcoffset() is None:
            raise ValueError("Aware evaluation time required")
        return self


class EvidenceDiagnostic(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    checks_passed: bool
    reason_codes: tuple[str, ...]
    evidence_digest: str
    production_trusted: Literal[False] = False
    human_approval_verified: Literal[False] = False
    execution_available: Literal[False] = False


def check_synthetic_evidence(bundle: SyntheticEvidence, *, now: datetime,
                             proposal_digest: str, review: SyntheticReviewBinding | None = None):
    if now.tzinfo is None or now.utcoffset() is None:
        raise ValueError("Aware evaluation time required")
    reasons = []
    if not bundle.clock_synchronized:
        reasons.append("CLOCK_UNVERIFIED")
    if bundle.symbol != bundle.quote_symbol:
        reasons.append("QUOTE_SYMBOL_MISMATCH")
    if bundle.quote_status != "ACTIVE":
        reasons.append("QUOTE_STATUS")
    if bundle.bid is None or bundle.ask is None or bundle.bid > bundle.ask:
        reasons.append("QUOTE_BID_ASK")
    event, receipt = bundle.quote_event_time, bundle.quote_received_time
    if (event is None or receipt is None or event > receipt or receipt > now
            or (now-event).total_seconds() < 0 or (now-event).total_seconds() > 30):
        reasons.append("QUOTE_TIME")
    cutoff = bundle.snapshot_cutoff
    if (cutoff is None or (now-cutoff).total_seconds() < 0
            or (now-cutoff).total_seconds() > 60):
        reasons.append("SNAPSHOT_TIME")
    if not bundle.snapshot_complete or not bundle.snapshot_reconciled:
        reasons.append("SNAPSHOT_INCOMPLETE")
    if not bundle.calendar_verified or not bundle.broker_regular_session_supported:
        reasons.append("SESSION_UNVERIFIED")
    if (bundle.session_open is None or not bundle.session_open <= now < bundle.session_close
            or now.astimezone(NY).date() != bundle.session_date):
        reasons.append("OUTSIDE_REGULAR_SESSION")
    digest = bundle.digest()
    if review is not None:
        if review.evidence_digest != digest or review.proposal_digest != proposal_digest:
            reasons.append("REVIEW_BINDING_CHANGED")
        age = (now-review.risk_evaluated_at).total_seconds()
        if age < 0 or age >= 300:
            reasons.append("REVIEW_EXPIRED")
    else:
        reasons.append("REVIEW_MISSING")
    return EvidenceDiagnostic(checks_passed=not reasons, reason_codes=tuple(reasons),
                              evidence_digest=digest)
