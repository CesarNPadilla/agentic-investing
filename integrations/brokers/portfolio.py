"""Read-only complete-state contract for future verified broker adapters.

The existing Webull reader does not implement this contract. Adapters must exhaust
pagination, preserve unavailable fields as None, and declare incomplete reads.
Never translate request errors into empty collections or promote buying power to cash.
"""

from datetime import datetime
from typing import Protocol

from portfolio.state import PortfolioState


class PortfolioReader(Protocol):
    def read_state(self, *, history_start: datetime) -> PortfolioState:
        """Return all accounts and posted events in (history_start, as_of].

        One consistent cutoff is required across accounts, balances, marks, orders
        and history. Failed/unsupported reads raise BrokerUnavailable or return
        explicit incomplete state. Broker-reported cash semantics must be verified.
        """
        ...
