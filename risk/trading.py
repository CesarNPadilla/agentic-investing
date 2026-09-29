"""Versioned deterministic rules for the synthetic execution account."""

from decimal import Decimal


def evaluate_trade(order, account):
    reasons = []
    quantity, price = Decimal(order["quantity"]), Decimal(order["limit_price"])
    notional = quantity * price
    held = Decimal(account["positions"].get(order["symbol"], "0"))
    if account["killed"]:
        reasons.append("Kill switch enabled")
    if order["symbol"] not in {"AAPL", "MSFT", "SPY"}:
        reasons.append("Symbol not allowed")
    if notional > Decimal(1000):
        reasons.append("Order exceeds 1000 USD limit")
    if order["side"] == "buy" and notional > Decimal(account["cash"]):
        reasons.append("Insufficient synthetic cash")
    if order["side"] == "buy" and (held + quantity) * price > Decimal(2500):
        reasons.append("Position exceeds 2500 USD at proposed limit price")
    if order["side"] == "sell" and quantity > held:
        reasons.append("Short selling forbidden")
    return {"version": "synthetic-risk-v1", "passed": not reasons, "reasons": reasons}
