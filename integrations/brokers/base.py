"""Future read-only integration contract. Never wired into the Phase 1 runtime."""

from typing import Protocol

from portfolio.models import Account, CashBalance, Position


class AccountNotFound(ValueError):
    """The requested account is not available from this reader."""


class BrokerUnavailable(RuntimeError):
    """The reader cannot currently retrieve account data."""


class BrokerReader(Protocol):
    """Return normalized reads; unknown account IDs raise AccountNotFound.

    Adapters translate transport failures to BrokerUnavailable. Empty lists mean
    successful reads with no holdings/balances, never a failed request.
    """

    def get_accounts(self) -> list[Account]: ...
    def get_positions(self, account_id: str) -> list[Position]: ...
    def get_cash(self, account_id: str) -> list[CashBalance]: ...


# Order submission/cancellation belong to a future, separately approved execution service.
