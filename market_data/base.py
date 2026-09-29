from typing import Protocol

from market_data.models import Quote


class SymbolNotFound(ValueError):
    pass


class ProviderUnavailable(RuntimeError):
    pass


class MarketDataProvider(Protocol):
    def get_quote(self, symbol: str) -> Quote: ...
