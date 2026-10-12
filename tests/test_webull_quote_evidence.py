import json
from datetime import UTC, datetime

import pytest

from market_data.webull_evidence import parse_sandbox_depth

NOW = datetime(2026, 10, 7, 18, 0, tzinfo=UTC)


def row():
    return {
        "symbol": "SCHB",
        "quote_time": int(NOW.timestamp() * 1000),
        "bids": [{"price": "29.85", "size": "100"}],
        "asks": [{"price": "29.86", "size": "100"}],
    }


def test_fresh_quote_preserves_unknown_schema_and_execution_block():
    report = parse_sandbox_depth(json.dumps(row()).encode(), received_at=NOW)
    assert report["age_seconds"] == 0
    assert "TIMESTAMP_SCHEMA_UNQUALIFIED" in report["blockers"]
    assert "MARKET_STATUS_UNVERIFIED" in report["blockers"]
    assert report["execution_available"] is False


@pytest.mark.parametrize(
    "change",
    [
        {"symbol": "INTC"},
        {"quote_time": True},
        {"quote_time": "1791396000000"},
        {"quote_time": int(NOW.timestamp() * 1000) + 1},
        {"quote_time": int(NOW.timestamp() * 1000) - 30001},
        {"bids": []},
        {"asks": [{"price": "0", "size": "100"}]},
        {"bids": [{"price": "NaN", "size": "100"}]},
        {"bids": [{"price": "30", "size": "100"}]},
        {"asks": [{"price": "29.86", "size": "0"}]},
    ],
)
def test_invalid_foreign_stale_future_or_crossed_data_rejected(change):
    data = row() | change
    with pytest.raises(ValueError):
        parse_sandbox_depth(json.dumps(data).encode(), received_at=NOW)


def test_depth_best_prices_do_not_assume_provider_sort_order():
    data = row()
    data["bids"].insert(0, {"price": "29.84", "size": "1"})
    assert parse_sandbox_depth(json.dumps(data).encode(), received_at=NOW)["bid"] == "29.85"
