"""Print synthetic Phase 3 API input; no network or credentials needed."""

import json
from datetime import UTC, datetime, timedelta

bars, benchmark = [], []
day = datetime(2020, 1, 1, 21, tzinfo=UTC)
while len(bars) < 120:
    if day.weekday() < 5:
        i = len(bars)
        bars.append({"timestamp": day.isoformat(), "close": str(100 + (i % 30) - i // 30)})
        benchmark.append({"timestamp": day.isoformat(), "close": str(100 + i / 10)})
    day += timedelta(days=1)

print(json.dumps({
    "strategy": {"name": "sma", "version": "1", "fast": 5, "slow": 20},
    "initial_cash": "10000", "fee_bps": "5", "slippage_bps": "10",
    "history": {"symbol": "AAPL", "source": "synthetic-example", "adjustment": "all",
                "is_sample": True, "bars": bars},
    "benchmark": {"symbol": "SPY", "source": "synthetic-example", "adjustment": "all",
                  "is_sample": True, "bars": benchmark},
}))
