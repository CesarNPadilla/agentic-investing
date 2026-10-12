from datetime import UTC, datetime
from pathlib import Path

from market_data.nyse_calendar import NysePublishedCalendar
from risk.paper_settlement import simulated_settlement

CAL = NysePublishedCalendar(Path(__file__).resolve().parents[1] / "conf/nyse-calendar-2026.json")


def ledger(day="2026-11-25", cutoff="2026-11-25T21:00:00+00:00"):
    row = {
        "activity_type": "FILL",
        "id": "sale",
        "order_id": "s",
        "symbol": "INTC",
        "side": "sell",
        "qty": "1",
        "price": "30",
        "cum_qty": "1",
        "leaves_qty": "0",
        "transaction_time": day + "T20:00:00+00:00",
    }
    buy = dict(row, id="buy", order_id="b", side="buy", transaction_time=day + "T15:00:00+00:00")
    return {
        "opening_cash": "1000",
        "baseline_at": "2026-10-05T14:00:00+00:00",
        "acquisition_cutoff": cutoff,
        "activities": {"b": {"row": buy}, "s": {"row": row}},
    }


def test_sale_stays_unavailable_over_holiday_then_releases_on_early_close_day():
    x = ledger()
    before = simulated_settlement(x, CAL, now=datetime(2026, 11, 26, 20, tzinfo=UTC))
    assert (
        before["simulated_settled_cash"] == "970"
        and before["simulated_unsettled_sale_proceeds"] == "30"
    )
    after = simulated_settlement(
        x, CAL, now=datetime(2026, 11, 27, 5, tzinfo=UTC), reserved_cash=25
    )
    assert after["simulated_settled_cash"] == "1000" and after["simulated_unreserved_cash"] == "975"
    assert not after["production_settlement_verified"] and not after["execution_available"]


def test_year_end_unknown_calendar_keeps_sales_unavailable():
    x = ledger("2026-12-31", "2026-12-31T21:00:00+00:00")
    report = simulated_settlement(x, CAL, now=datetime(2027, 1, 4, 20, tzinfo=UTC))
    assert "SETTLEMENT_CALENDAR_COVERAGE" in report["blockers"]
    assert report["simulated_settled_cash"] == "970"


def test_unexplained_flow_and_reserved_cash_block():
    x = ledger()
    x["activities"]["deposit"] = {
        "row": {"activity_type": "CSD", "net_amount": "100", "date": "2026-11-25T18:00:00+00:00"}
    }
    report = simulated_settlement(
        x, CAL, now=datetime(2026, 11, 26, 20, tzinfo=UTC), reserved_cash=1000
    )
    assert {
        "EXTERNAL_FLOW_REQUIRES_HUMAN_RECONCILIATION",
        "SIMULATED_CASH_RESERVATIONS_EXCEED_AVAILABLE",
    } <= set(report["blockers"])
