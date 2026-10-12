from datetime import UTC, datetime
from decimal import Decimal

import pytest

from portfolio.paper_cash_reconciliation import cash_activity

BASELINE = datetime(2026, 10, 5, 15, tzinfo=UTC)
CUTOFF = datetime(2026, 10, 7, 15, tzinfo=UTC)


@pytest.mark.parametrize("value", ["100", "-100"])
def test_executed_usd_cash_journal_maps_signed_effect_without_settlement_claim(value):
    row = {
        "activity_type": "JNLC",
        "currency": "USD",
        "status": "executed",
        "net_amount": value,
        "date": "2026-10-06",
    }
    effect, reason = cash_activity(row, baseline=BASELINE, cutoff=CUTOFF)
    assert reason is None and effect["external_flow"] == Decimal(value)


def test_baseline_day_and_creation_timestamp_do_not_resolve_effective_date():
    row = {
        "activity_type": "JNLC",
        "currency": "USD",
        "status": "executed",
        "net_amount": "1000",
        "date": "2026-10-05",
        "created_at": "2026-10-05T14:00:00Z",
    }
    effect, reason = cash_activity(row, baseline=BASELINE, cutoff=CUTOFF)
    assert effect is None and reason == "CASH_ACTIVITY_BASELINE_DAY_AMBIGUOUS"


@pytest.mark.parametrize("changes", [{"currency": "EUR"}, {"status": "pending"}])
def test_unqualified_cash_journal_never_applies(changes):
    row = {
        "activity_type": "JNLC",
        "currency": "USD",
        "status": "executed",
        "net_amount": "100",
        "date": "2026-10-06",
        **changes,
    }
    effect, reason = cash_activity(row, baseline=BASELINE, cutoff=CUTOFF)
    assert effect is None and reason == "CASH_JOURNAL_UNQUALIFIED"
