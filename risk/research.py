"""Deterministic data-quality checks, not a trading authorization engine."""

from datetime import datetime, timedelta

from market_data.models import Quote


def quote_warnings(quote: Quote, now: datetime) -> list[str]:
    warnings = []
    if quote.is_sample:
        warnings.append("Synthetic sample data; not suitable for investment decisions.")
    if quote.as_of > now:
        warnings.append("Quote timestamp is in the future.")
    elif now - quote.as_of > timedelta(days=1):
        warnings.append("Quote is older than 24 hours; freshness requires review.")
    return warnings
