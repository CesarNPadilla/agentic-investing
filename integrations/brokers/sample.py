"""Synthetic read-only broker fixture; no network or credentials required."""

from decimal import Decimal

from integrations.brokers.base import AccountNotFound
from portfolio.models import Account, CashBalance, Position


class SampleBrokerReader:
    """Fixed fictional account data, not a real portfolio or current valuation.

    Kept separate from the research runtime and market-data provider.
    """

    account_id = "synthetic-account-001"

    def get_accounts(self) -> list[Account]:
        return [Account(account_id=self.account_id, currency="USD")]

    def _check_account(self, account_id: str) -> None:
        if account_id != self.account_id:
            raise AccountNotFound(account_id)

    def get_positions(self, account_id: str) -> list[Position]:
        self._check_account(account_id)
        return [Position(account_id=account_id, symbol="AAPL", quantity=Decimal("2.5"))]

    def get_cash(self, account_id: str) -> list[CashBalance]:
        self._check_account(account_id)
        return [CashBalance(account_id=account_id, currency="USD", amount=Decimal("1000.00"))]
