"""Diagnostic SCHB depth evidence; timestamp interpretation never grants trading."""

import hashlib
import json
from datetime import UTC, datetime, timedelta
from decimal import Decimal, InvalidOperation


def parse_sandbox_depth(raw: bytes, *, received_at: datetime):
    try:
        return _parse_depth(raw, received_at=received_at)
    except (KeyError, ValueError, TypeError, InvalidOperation, OverflowError):
        raise ValueError("Webull sandbox quote unavailable or invalid") from None


def _parse_depth(raw: bytes, *, received_at: datetime):
    if received_at.tzinfo is None or received_at.utcoffset() is None:
        raise ValueError("Aware receipt timestamp required")
    row = json.loads(raw, parse_float=Decimal)
    if not isinstance(row, dict) or row.get("symbol") != "SCHB":
        raise ValueError("Frozen ETF symbol required")
    prices = {}
    for side in ("bids", "asks"):
        levels = row.get(side)
        if not isinstance(levels, list) or not levels:
            raise ValueError("Depth required")
        parsed = []
        for level in levels:
            if not isinstance(level, dict):
                raise TypeError("Invalid depth")
            if isinstance(level.get("price"), bool) or isinstance(level.get("size"), bool):
                raise TypeError("Invalid numeric field")
            price, size = Decimal(str(level["price"])), Decimal(str(level["size"]))
            if not price.is_finite() or not size.is_finite() or price <= 0 or size <= 0:
                raise ValueError("Positive finite depth required")
            parsed.append(price)
        prices[side] = parsed
    bid, ask = max(prices["bids"]), min(prices["asks"])
    if bid > ask:
        raise ValueError("Crossed quote")
    timestamp = row.get("quote_time")
    if type(timestamp) is not int or timestamp <= 0:
        raise ValueError("Strict integer timestamp required")
    # Preserve the unqualified provider-unit assumption explicitly.
    event = datetime(1970, 1, 1, tzinfo=UTC) + timedelta(milliseconds=timestamp)
    age = (received_at - event).total_seconds()
    if not 0 <= age <= 30:
        raise ValueError("Future or stale quote")
    return {
        "source": "WEBULL_RETAIL_SANDBOX_DEPTH",
        "symbol": "SCHB",
        "bid": str(bid),
        "ask": str(ask),
        "quote_time_raw": timestamp,
        "timestamp_interpretation": "UNIX_MILLISECONDS_UNQUALIFIED",
        "event_time_utc": event.isoformat(),
        "received_at_utc": received_at.astimezone(UTC).isoformat(),
        "age_seconds": age,
        "raw_sha256": hashlib.sha256(raw).hexdigest(),
        "blockers": [
            "TIMESTAMP_SCHEMA_UNQUALIFIED",
            "MARKET_STATUS_UNVERIFIED",
            "CLOCK_RUNTIME_UNQUALIFIED",
            "RUNTIME_INTEGRATION_PENDING",
        ],
        "execution_available": False,
        "trial_started": False,
    }
