"""Full NY-calendar-day activity retention; published pages aren't completeness proof."""

import hashlib
import json
from datetime import datetime
from decimal import Decimal

from portfolio.paper_cash_reconciliation import cash_activity
from portfolio.paper_fill_reconciliation import PaperFill
from risk.paper_daily_loss import NY, BoundaryEvidence
from risk.paper_state import PaperStateError


def retain_daily_activity(store, batch, *, account_binding):
    """Separate daily coverage from the ledger's intraday initial cash baseline.

    External-flow totals remain diagnostic until publication and snapshot
    coherence are qualified. Empty pages never supply a trusted zero to risk.
    """
    day = batch.after.astimezone(NY).date().isoformat()
    blockers = {"DAILY_ACTIVITY_PUBLICATION_UNVERIFIED"}
    with store.transaction() as state:
        if account_binding != state["binding"]:
            raise PaperStateError("Daily activity account changed")
        baseline = BoundaryEvidence.model_validate(
            state.get("paper_day_boundary_evidence", {}).get(day, {})
        )
        if (
            baseline.account_binding != account_binding
            or batch.after != baseline.as_of
            or batch.until.astimezone(NY).date().isoformat() != day
            or batch.until <= batch.after
            or batch.received_at < batch.until
            or not batch.pagination_exhausted
        ):
            raise PaperStateError("Incomplete daily acquisition window")
        records = state.setdefault("paper_daily_activity", {})
        record = records.setdefault(day, {"until": batch.after.isoformat(), "activities": {}})
        if batch.until < datetime.fromisoformat(record["until"]):
            raise PaperStateError("Daily acquisition cutoff regressed")
        seen = set()
        for row in batch.rows:
            identifier = row.get("id")
            if not isinstance(identifier, str) or not identifier or identifier in seen:
                raise PaperStateError("Invalid or duplicate daily activity identity")
            seen.add(identifier)
            digest = hashlib.sha256(json.dumps(row, sort_keys=True).encode()).hexdigest()
            previous = record["activities"].get(identifier)
            if previous and previous["digest"] != digest:
                raise PaperStateError("Daily activity correction requires human review")
            record["activities"][identifier] = {"digest": digest, "row": row}
        total, fees = Decimal(0), Decimal(0)
        if set(record["activities"]) - seen:
            blockers.add("DAILY_ACTIVITY_MISSING_FROM_FRESH_READ")
        for item in record["activities"].values():
            row = item["row"]
            if row.get("activity_type") == "FILL":
                fill = PaperFill.model_validate(row)
                if not baseline.as_of < fill.transaction_time <= batch.until:
                    raise PaperStateError("Daily fill outside acquisition interval")
                continue
            effect, reason = cash_activity(row, baseline=baseline.as_of, cutoff=batch.until)
            if reason:
                blockers.add(reason)
            else:
                total += effect["external_flow"]
                if effect["kind"] == "FEE":
                    fees -= effect["net_amount"]
        record.update(
            until=batch.until.isoformat(),
            received_at=batch.received_at.isoformat(),
            page_digests=list(batch.page_digests),
            observed_external_flow_total=str(total),
            observed_fee_total=str(fees),
            blockers=sorted(blockers),
        )
        state["latch_reasons"] = sorted(set(state["latch_reasons"]) | blockers)
    return {
        "activity_count": len(record["activities"]),
        "observed_external_flow_total": str(total),
        "observed_fee_total": str(fees),
        "external_flow_total_for_risk": None,
        "blockers": sorted(blockers),
        "execution_available": False,
    }
