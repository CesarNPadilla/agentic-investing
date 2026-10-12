"""Frozen deterministic paper intent generator; no research, order IO or approval."""

from decimal import ROUND_CEILING, Decimal

STRATEGY_ID = "PAPER_CONTROL_PLUMBING"
VERSION = "1.0.0"
SYMBOL = "INTC"


def candidate(
    *,
    ask,
    current_account_equity,
    current_sleeve_equity,
    settled_cash,
    has_position=False,
    has_open_order=False,
):
    values = [
        Decimal(str(x)) for x in (ask, current_account_equity, current_sleeve_equity, settled_cash)
    ]
    if any(not x.is_finite() or x <= 0 for x in values):
        return {"action": "HOLD", "reason": "INVALID_INPUT", "execution_available": False}
    price, account, sleeve, cash = values
    base = {
        "strategy_id": STRATEGY_ID,
        "version": VERSION,
        "symbol": SYMBOL,
        "execution_available": False,
    }
    if has_open_order or has_position:
        return dict(base, action="HOLD", reason="EXISTING_EXPOSURE_REQUIRES_RECONCILIATION")
    # Smallest whole-share test intent meeting the original $25 minimum order.
    quantity = int((Decimal(25) / price).to_integral_value(rounding=ROUND_CEILING))
    limit = min(
        Decimal(250),  # $250 fixed cap and 25% of the frozen $1,000 initial sleeve.
        sleeve * Decimal("0.25"),
        account * Decimal("0.10"),
        sleeve * Decimal("0.75"),
        cash,
    )
    if quantity * price > limit:
        return dict(base, action="HOLD", reason="MINIMUM_ORDER_EXCEEDS_CONTROLS")
    return dict(
        base,
        action="BUY_INTENT_ONLY",
        quantity=quantity,
        limit_price=str(price),
        reason="DETERMINISTIC_CONTROL_PROBE",
        requires_full_risk_review=True,
    )
