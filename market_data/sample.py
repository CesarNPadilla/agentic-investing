from datetime import UTC, datetime
from decimal import Decimal

from market_data.base import SymbolNotFound
from market_data.models import Quote


class SampleMarketDataProvider:
    """Synthetic fixture only. Values are not historical or current market prices."""

    def get_quote(self, symbol: str) -> Quote:
        if symbol != "AAPL":
            raise SymbolNotFound(symbol)
        return Quote(
            symbol=symbol,
            price=Decimal("100.00"),
            currency="USD",
            as_of=datetime(2026, 1, 1, tzinfo=UTC),
            source="synthetic-fixture-v1",
            is_sample=True,
        )
