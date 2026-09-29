"""Print a complete synthetic research request. Never reads accounts or credentials."""

import json
from datetime import UTC, datetime, timedelta
from pathlib import Path


def build():
    path = Path(__file__).with_name("research-evidence.json")
    evidence = json.loads(path.read_text(encoding="utf-8"))
    as_of = datetime(2026, 9, 27, 20, tzinfo=UTC)
    # Weekdays only; this synthetic calendar does not remove exchange holidays.
    days = []
    cursor = as_of - timedelta(days=1)
    while len(days) < 60:
        if cursor.weekday() < 5:
            days.append(cursor)
        cursor -= timedelta(days=1)
    evidence["price_history"] = {
        "symbol": "AAPL",
        "source": "synthetic-example-not-market-history",
        "adjustment": "split",
        "is_sample": True,
        "bars": [
            {"timestamp": day.isoformat(), "close": str(100 + index)}
            for index, day in enumerate(reversed(days))
        ],
    }
    evidence["portfolio"] = {
        "source": "synthetic-example-not-real-accounts",
        "as_of": as_of.isoformat(),
        "currency": "USD",
        "is_sample": True,
        "holdings": [
            {
                "account_id": "demo-one",
                "symbol": "AAPL",
                "quantity": "10",
                "price": "159",
                "currency": "USD",
                "price_as_of": days[0].isoformat(),
                "price_source": "synthetic-example",
                "sector": "Technology",
            },
            {
                "account_id": "demo-two",
                "symbol": "MSFT",
                "quantity": "5",
                "price": "100",
                "currency": "USD",
                "price_as_of": days[0].isoformat(),
                "price_source": "synthetic-example",
                "sector": "Technology",
            },
        ],
        "cash": [{"account_id": "demo-one", "currency": "USD", "amount": "2910"}],
    }
    return evidence


if __name__ == "__main__":
    print(json.dumps(build(), indent=2))
