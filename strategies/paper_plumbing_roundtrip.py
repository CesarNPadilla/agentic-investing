"""Frozen 1.1.0 paper plumbing sequence; produces intents, never permission."""

from datetime import date
from decimal import Decimal
from uuid import NAMESPACE_URL, uuid5

from strategies.paper_plumbing import candidate

VERSION = "1.1.0"


def next_intent(
    *,
    binding,
    day,
    last_entry_day,
    owned_quantity,
    observed_quantity,
    entry_terminal,
    has_open_order,
    regular_session,
    trial_ended,
    reconciliation_verified,
    bid,
    ask,
    account_equity,
    sleeve_equity,
    settled_cash,
):
    """Caller supplies reconciled durable state; outstanding orders block both sides.

    One entry per NYSE session, followed by an exit on a later observation after
    terminal entry reconciliation. Only shares attributed to this strategy exit.
    Existing 1.0.0 sizing stays frozen. Every intent still needs all runtime gates.
    """
    base = {
        "strategy_id": "PAPER_CONTROL_PLUMBING",
        "version": VERSION,
        "symbol": "INTC",
        "execution_available": False,
        "requires_full_risk_review": True,
    }

    def hold(reason):
        return dict(base, action="HOLD", reason=reason)

    try:
        if (
            len(binding) != 64
            or any(c not in "0123456789abcdef" for c in binding)
            or not isinstance(day, date)
            or (last_entry_day is not None and not isinstance(last_entry_day, date))
        ):
            return hold("INVALID_STATE")
        owned, observed, price = (Decimal(str(x)) for x in (owned_quantity, observed_quantity, bid))
        if (
            any(not x.is_finite() for x in (owned, observed, price))
            or owned < 0
            or observed < 0
            or price <= 0
            or owned != owned.to_integral_value()
            or observed != observed.to_integral_value()
        ):
            return hold("INVALID_STATE")
        if last_entry_day is not None and last_entry_day > day:
            return hold("STATE_DATE_REGRESSION")
        if trial_ended:
            return hold("TRIAL_ENDED_HUMAN_REVIEW")
        if not reconciliation_verified or owned > observed:
            return hold("OWNERSHIP_RECONCILIATION_REQUIRED")
        if has_open_order or not regular_session:
            return hold("ORDER_OR_SESSION_BLOCK")
        if owned:
            if not entry_terminal or last_entry_day is None:
                return hold("ENTRY_TERMINAL_RECONCILIATION_REQUIRED")
            if not Decimal(25) <= owned * price <= Decimal(100):
                return hold("EXIT_OUTSIDE_FROZEN_ORDER_BOUNDS")
            result = dict(
                base,
                action="SELL_INTENT_ONLY",
                quantity=int(owned),
                limit_price=str(price),
                reason="RECONCILED_PLUMBING_EXIT",
            )
            identity_day = last_entry_day
        else:
            if observed:
                return hold("FOREIGN_HOLDINGS_REQUIRE_HUMAN_REVIEW")
            if last_entry_day == day:
                return hold("DAILY_ROUNDTRIP_COMPLETE")
            result = candidate(
                ask=ask,
                current_account_equity=account_equity,
                current_sleeve_equity=sleeve_equity,
                settled_cash=settled_cash,
            )
            result.update(base)
            if result["action"] == "HOLD":
                return result
            identity_day = day
        result["client_order_id"] = str(
            uuid5(
                NAMESPACE_URL,
                f"paper-plumbing:{VERSION}:{binding}:{identity_day}:{result['action']}",
            )
        )
        return result
    except (ArithmeticError, TypeError, ValueError):
        return hold("INVALID_STATE")
