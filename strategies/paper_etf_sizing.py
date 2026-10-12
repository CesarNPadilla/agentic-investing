"""SCHB whole-share plumbing sizing; frozen intent-only ETF replacement."""

from decimal import ROUND_CEILING, Decimal


def candidate(*, ask, current_account_equity, current_sleeve_equity, settled_cash):
    base = {"symbol": "SCHB", "execution_available": False}
    try:
        price, account, sleeve, cash = (
            Decimal(str(x))
            for x in (ask, current_account_equity, current_sleeve_equity, settled_cash)
        )
        if any(not x.is_finite() or x <= 0 for x in (price, account, sleeve, cash)):
            return dict(base, action="HOLD", reason="INVALID_INPUT")
        # Round upward to a valid cent limit before checking minimum and all caps.
        price = price.quantize(Decimal("0.01"), rounding=ROUND_CEILING)
        quantity = int((Decimal(25) / price).to_integral_value(rounding=ROUND_CEILING))
        cap = min(
            Decimal(250),
            sleeve * Decimal("0.25"),
            account * Decimal("0.10"),
            sleeve * Decimal("0.75"),
            cash,
            Decimal(100),
        )
        if quantity * price > cap:
            return dict(base, action="HOLD", reason="MINIMUM_ORDER_EXCEEDS_CONTROLS")
        return dict(
            base,
            action="BUY_INTENT_ONLY",
            quantity=quantity,
            limit_price=str(price),
            reason="DETERMINISTIC_CONTROL_PROBE",
            requires_full_risk_review=True,
        )
    except (ArithmeticError, TypeError, ValueError):
        return dict(base, action="HOLD", reason="INVALID_INPUT")
