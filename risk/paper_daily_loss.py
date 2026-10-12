"""Durable paper daily-loss diagnostics; unqualified evidence remains blocked."""

from datetime import datetime, time
from decimal import Decimal
from typing import Literal
from zoneinfo import ZoneInfo

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, model_validator

from risk.paper_state import PaperStateError

NY = ZoneInfo("America/New_York")


class BoundaryEvidence(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    account_binding: str = Field(pattern=r"^[0-9a-f]{64}$")
    source_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    source_description: str = Field(min_length=1)
    source_kind: Literal["UNQUALIFIED", "ALPACA_PAPER_CONTINUOUS_HISTORY"] = "UNQUALIFIED"
    as_of: AwareDatetime
    equity: Decimal = Field(gt=0, allow_inf_nan=False)

    @model_validator(mode="after")
    def midnight(self):
        if self.as_of.astimezone(NY).time() != time(0):
            raise ValueError("Exact New York calendar midnight evidence required")
        return self


def retain_boundary_evidence(store, evidence):
    """Retain immutable source evidence; generic source claims stay unqualified.

    Existing Alpaca account reads lack a broker equity-as-of midnight timestamp;
    their request/receipt times cannot be substituted for this evidence.
    """
    evidence = BoundaryEvidence.model_validate(evidence.model_dump())
    row = evidence.model_dump(mode="json")
    day = evidence.as_of.astimezone(NY).date().isoformat()
    with store.transaction() as state:
        if state["binding"] != evidence.account_binding:
            raise PaperStateError("Daily baseline account mismatch")
        records = state.setdefault("paper_day_boundary_evidence", {})
        if day in records and records[day] != row:
            raise PaperStateError("Daily baseline correction requires human review")
        records[day] = row


def evaluate_daily_loss(store, observation, *, now, external_flow_total=None):
    if not isinstance(now, datetime) or now.tzinfo is None or now.utcoffset() is None:
        raise ValueError("Aware evaluation time required")
    reasons = set()
    pnl, threshold, breach = None, None, False
    with store.transaction() as state:
        if observation.account_binding_sha256 != state["binding"]:
            raise PaperStateError("Daily-loss account changed")
        row = state.get("paper_day_boundary_evidence", {}).get(
            now.astimezone(NY).date().isoformat()
        )
        if row is None:
            reasons.add("DAILY_MIDNIGHT_BASELINE_UNVERIFIED")
            reasons.add("DAILY_BOUNDARY_SOURCE_UNQUALIFIED")
        else:
            baseline = BoundaryEvidence.model_validate(row)
            if baseline.source_kind != "ALPACA_PAPER_CONTINUOUS_HISTORY":
                reasons.add("DAILY_BOUNDARY_SOURCE_UNQUALIFIED")
            if baseline.account_binding != state["binding"]:
                raise PaperStateError("Stored baseline account changed")
            if baseline.as_of.astimezone(NY).date() != now.astimezone(NY).date():
                raise PaperStateError("Stored baseline belongs to another New York day")
            threshold = baseline.equity * Decimal("0.01")
            if (
                not baseline.as_of <= observation.started_at <= observation.received_at <= now
                or (now - observation.started_at).total_seconds() > 60
                or not observation.bracket_stable
                or not observation.account_unblocked
            ):
                reasons.add("DAILY_LOSS_SNAPSHOT_UNQUALIFIED")
            elif external_flow_total is None:
                reasons.add("DAILY_EXTERNAL_FLOWS_UNRECONCILED")
            else:
                flows = Decimal(str(external_flow_total))
                if not flows.is_finite():
                    raise PaperStateError("Invalid external flow total")
                pnl = observation.equity - baseline.equity - flows
                breach = pnl <= -threshold
                if breach:
                    reasons.add("ACCOUNT_DAILY_LOSS")
        state["latch_reasons"] = sorted(set(state["latch_reasons"]) | reasons)
    return {
        "daily_net_pnl": str(pnl) if pnl is not None else None,
        "daily_loss_limit": str(threshold) if threshold is not None else None,
        "daily_loss_breach": breach,
        "daily_pnl_evaluated": pnl is not None,
        "blockers": sorted(reasons),
        "execution_available": False,
        "automatic_liquidation": False,
    }
