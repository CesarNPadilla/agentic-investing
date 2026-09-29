"""Read-only complete-state contract for future verified broker adapters.

The Webull reader implements this contract with explicit incomplete-ledger and
non-atomic-read flags. Adapters must exhaust pagination and preserve unavailable fields as None.
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
