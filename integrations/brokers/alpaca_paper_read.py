"""Paper-only bracketed account observations. No fills/settlement trust or mutations."""

import hashlib
import json
from datetime import UTC, datetime
from decimal import Decimal
from typing import Literal

import httpx
from pydantic import AwareDatetime, BaseModel, ConfigDict, Field

from market_data.base import ProviderUnavailable
from market_data.models import Symbol

PAPER = "https://paper-api.alpaca.markets"


class PaperPosition(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    symbol: Symbol
    quantity: Decimal = Field(allow_inf_nan=False)
    market_value: Decimal = Field(allow_inf_nan=False)


class PaperAccountObservation(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    account_binding_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    payload_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    started_at: AwareDatetime
    received_at: AwareDatetime
    equity: Decimal = Field(allow_inf_nan=False)
    cash: Decimal = Field(allow_inf_nan=False)
    positions_count: int = Field(ge=0)
    open_orders_count: int = Field(ge=0)
    bracket_stable: bool
    account_unblocked: bool
    positions_market_value: Decimal = Field(ge=0, allow_inf_nan=False)
    position_quantities: tuple[PaperPosition, ...] = ()
    empty_inventory: bool
    transaction_ledger_reconciled: Literal[False] = False
    settled_cash_verified: Literal[False] = False
    execution_available: Literal[False] = False

    def reasons(self, now):
        if now.tzinfo is None or now.utcoffset() is None:
            raise ValueError("Aware time required")
        reasons = ["TRANSACTION_LEDGER_UNRECONCILED", "SETTLED_CASH_UNVERIFIED"]
        if not self.bracket_stable:
            reasons.append("ACCOUNT_CHANGED_DURING_READ")
        if not self.account_unblocked:
            reasons.append("ACCOUNT_BLOCKED")
        if (
            not self.started_at <= self.received_at <= now
            or (now - self.started_at).total_seconds() > 60
        ):
            reasons.append("ACCOUNT_SNAPSHOT_TIME")
        if not self.empty_inventory:
            reasons.append("NONEMPTY_INVENTORY_RECONCILIATION_REQUIRED")
        return tuple(reasons)


class AlpacaPaperAccountReader:
    def __init__(self, key, secret, *, transport=None, clock=None):
        if not key or not secret:
            raise ValueError("Credentials required")
        self._headers = {"APCA-API-KEY-ID": key, "APCA-API-SECRET-KEY": secret}
        self._transport = transport
        self._clock = clock or (lambda: datetime.now(UTC))

    def observe(self):
        started = self._clock()
        raw = []
        try:
            with httpx.Client(
                timeout=15, transport=self._transport, follow_redirects=False
            ) as client:

                def get(path, params=None):
                    response = client.get(PAPER + path, headers=self._headers, params=params)
                    if response.status_code != 200:
                        raise ValueError("Read failed")
                    raw.append(hashlib.sha256(response.content).hexdigest())
                    return json.loads(response.content, parse_float=Decimal)

                before = get("/v2/account")
                positions = get("/v2/positions")
                orders = get("/v2/orders", {"status": "open", "limit": 500, "nested": "true"})
                after = get("/v2/account")
            if not isinstance(before, dict) or not isinstance(after, dict):
                raise TypeError()
            if (
                not isinstance(positions, list)
                or not isinstance(orders, list)
                or len(orders) >= 500
            ):
                raise ValueError("Inventory malformed or potentially truncated")
            # Full account response equality is conservative, not an atomic provider guarantee.
            stable = before == after
            identifier = before["id"]
            if not isinstance(identifier, str) or not identifier or after["id"] != identifier:
                raise ValueError("Account binding changed")
            symbols = [p["symbol"] for p in positions]
            ids = [o["id"] for o in orders]
            if len(set(symbols)) != len(symbols) or len(set(ids)) != len(ids):
                raise ValueError()
            marked = sum((abs(Decimal(p["market_value"])) for p in positions), Decimal(0))
            return PaperAccountObservation(
                account_binding_sha256=hashlib.sha256(identifier.encode()).hexdigest(),
                payload_sha256=hashlib.sha256("\n".join(raw).encode()).hexdigest(),
                started_at=started,
                received_at=self._clock(),
                equity=before["equity"],
                cash=before["cash"],
                positions_count=len(positions),
                open_orders_count=len(orders),
                bracket_stable=stable,
                account_unblocked=before.get("status") == "ACTIVE"
                and all(
                    before.get(f) is False
                    for f in ("trading_blocked", "account_blocked", "trade_suspended_by_user")
                ),
                positions_market_value=marked,
                empty_inventory=not positions and not orders,
                position_quantities=tuple(
                    PaperPosition(
                        symbol=p["symbol"], quantity=p["qty"], market_value=p["market_value"]
                    )
                    for p in positions
                ),
            )
        except (httpx.HTTPError, ValueError, KeyError, TypeError, ArithmeticError):
            raise ProviderUnavailable("Paper account observation unavailable or invalid") from None
