"""Explicit cash activity classification and account comparison; no settlement claim."""

from datetime import date, datetime
from decimal import Decimal
from zoneinfo import ZoneInfo

from pydantic import AwareDatetime, TypeAdapter

NY = ZoneInfo("America/New_York")


def cash_activity(row, *, baseline, cutoff):
    kind = row.get("activity_type")
    if kind not in {"FEE", "CSD", "CSW", "JNLC"}:
        return None, "UNMAPPED_CASH_ACTIVITY"
    if kind == "JNLC" and (row.get("currency") != "USD" or row.get("status") != "executed"):
        return None, "CASH_JOURNAL_UNQUALIFIED"
    value = Decimal(str(row.get("net_amount")))
    if not value.is_finite():
        raise ValueError("Finite cash effect required")
    if (kind in {"FEE", "CSW"} and value > 0) or (kind == "CSD" and value < 0):
        raise ValueError("Cash activity sign contradicts type")
    raw_time = row.get("date")
    try:
        day = date.fromisoformat(raw_time)
    except (ValueError, TypeError):
        instant = TypeAdapter(AwareDatetime).validate_python(raw_time)
        if not baseline < instant <= cutoff:
            return None, "CASH_ACTIVITY_OUTSIDE_BASELINE"
    else:
        # A date alone cannot locate an event relative to an intraday bootstrap.
        if day == baseline.astimezone(NY).date():
            return None, "CASH_ACTIVITY_BASELINE_DAY_AMBIGUOUS"
        if day < baseline.astimezone(NY).date() or day > cutoff.astimezone(NY).date():
            return None, "CASH_ACTIVITY_OUTSIDE_BASELINE"
        if day == cutoff.astimezone(NY).date():
            return None, "CASH_ACTIVITY_CUTOFF_DAY_AMBIGUOUS"
    return {
        "net_amount": value,
        "kind": kind,
        "external_flow": value if kind in {"CSD", "CSW", "JNLC"} else Decimal(0),
    }, None


def reconcile_cash(ledger, observation, *, now, ledger_binding=None):
    if now.tzinfo is None or now.utcoffset() is None:
        raise ValueError("Aware comparison time required")
    baseline = datetime.fromisoformat(ledger["baseline_at"])
    cutoff = datetime.fromisoformat(ledger["acquisition_cutoff"])
    expected = Decimal(ledger["trade_cash"])
    if not expected.is_finite():
        raise ValueError("Finite ledger cash required")
    reasons = {"SETTLED_CASH_UNVERIFIED", "PUBLICATION_COMPLETENESS_UNVERIFIED"}
    if ledger_binding is None or ledger_binding != observation.account_binding_sha256:
        reasons.add("ACCOUNT_BINDING_UNVERIFIED")
    fees, flows, applied = Decimal(0), Decimal(0), 0
    for item in ledger["activities"].values():
        row = item["row"]
        if row.get("activity_type") == "FILL":
            continue
        effect, reason = cash_activity(row, baseline=baseline, cutoff=cutoff)
        if reason:
            reasons.add(reason)
            continue
        expected += effect["net_amount"]
        flows += effect["external_flow"]
        if effect["kind"] == "FEE":
            fees -= effect["net_amount"]
        applied += 1
    age = (now - observation.started_at).total_seconds()
    if not observation.started_at <= observation.received_at <= now or not 0 <= age <= 60:
        reasons.add("ACCOUNT_SNAPSHOT_TIME")
    if not observation.bracket_stable or not observation.account_unblocked:
        reasons.add("ACCOUNT_SNAPSHOT_UNQUALIFIED")
    if cutoff > observation.started_at:
        reasons.add("LEDGER_CUTOFF_AFTER_SNAPSHOT")
    elif cutoff < observation.started_at:
        reasons.add("LEDGER_SNAPSHOT_CUTOFF_GAP")
    cash_matches = expected == observation.cash
    if not cash_matches:
        reasons.add("ACCOUNT_CASH_LEDGER_MISMATCH")
    if observation.positions_count:
        if len(observation.position_quantities) != observation.positions_count:
            positions_match = False
            reasons.add("POSITION_QUANTITY_EVIDENCE_REQUIRED")
        else:
            quantities = {
                p.symbol: p.quantity for p in observation.position_quantities if p.quantity
            }
            if (
                len({p.symbol for p in observation.position_quantities})
                != observation.positions_count
            ):
                reasons.add("POSITION_DUPLICATE_SYMBOL")
            positions_match = quantities == {
                k: Decimal(v) for k, v in ledger["positions"].items() if Decimal(v)
            }
            if not positions_match:
                reasons.add("ACCOUNT_POSITION_LEDGER_MISMATCH")
    else:
        positions_match = not ledger["positions"]
        if not positions_match:
            reasons.add("ACCOUNT_POSITION_LEDGER_MISMATCH")
    return {
        "cash_matches": cash_matches,
        "positions_match": positions_match,
        "cash_activities_mapped": applied,
        "fee_total": str(fees),
        "external_flow_total": str(flows),
        "blockers": sorted(reasons),
        "execution_available": False,
        "settlement_verified": False,
    }
