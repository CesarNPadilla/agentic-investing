"""Owner-approved paper-only settled-cash model, no production settlement claim."""

from datetime import datetime
from decimal import Decimal
from zoneinfo import ZoneInfo

from market_data.nyse_calendar import CalendarCoverageError
from portfolio.paper_cash_reconciliation import cash_activity
from portfolio.paper_fill_reconciliation import PaperFill

NY = ZoneInfo("America/New_York")


def simulated_settlement(ledger, calendar, *, now, reserved_cash=0):
    if now.tzinfo is None or now.utcoffset() is None:
        raise ValueError("Aware simulation time required")
    reserved = Decimal(str(reserved_cash))
    if not reserved.is_finite() or reserved < 0:
        raise ValueError("Finite nonnegative reservation required")
    settled = Decimal(ledger["opening_cash"])
    if settled != 1000:
        raise ValueError("Dedicated verified initial $1,000 required")
    baseline = datetime.fromisoformat(ledger["baseline_at"])
    cutoff = datetime.fromisoformat(ledger["acquisition_cutoff"])
    reasons = set()
    if now < baseline or now < cutoff:
        reasons.add("SETTLEMENT_TIME_REGRESSION")
    pending = Decimal(0)
    for value in ledger["activities"].values():
        row = value["row"]
        if row.get("activity_type") == "FILL":
            fill = PaperFill.model_validate(row)
            if not baseline < fill.transaction_time <= cutoff or fill.transaction_time > now:
                reasons.add("SETTLEMENT_FILL_TIME")
                continue
            cost = fill.qty * fill.price
            if fill.side == "buy":
                settled -= cost
            else:
                try:
                    release = calendar.next_trading_day(fill.transaction_time.astimezone(NY).date())
                except CalendarCoverageError:
                    reasons.add("SETTLEMENT_CALENDAR_COVERAGE")
                    pending += cost
                    continue
                if now.astimezone(NY).date() >= release:
                    settled += cost
                else:
                    pending += cost
        else:
            effect, reason = cash_activity(row, baseline=baseline, cutoff=cutoff)
            if reason:
                reasons.add(reason)
            elif effect["kind"] == "FEE":
                settled += effect["net_amount"]
            else:
                reasons.add("EXTERNAL_FLOW_REQUIRES_HUMAN_RECONCILIATION")
    if settled < 0:
        reasons.add("SIMULATED_SETTLED_CASH_OVERDRAWN")
    if reserved > max(settled, Decimal(0)):
        reasons.add("SIMULATED_CASH_RESERVATIONS_EXCEED_AVAILABLE")
    return {
        "model": "OWNER_APPROVED_PAPER_ONLY_NEXT_NYSE_DAY",
        "simulated_settled_cash": str(max(settled, Decimal(0))),
        "simulated_unsettled_sale_proceeds": str(pending),
        "simulated_unreserved_cash": str(max(settled - reserved, Decimal(0))),
        "blockers": sorted(reasons),
        "production_settlement_verified": False,
        "execution_available": False,
    }
