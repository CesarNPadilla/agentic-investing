"""Local synthetic execution adapter; never sends network orders.

The service commits the returned account and receipt in the approval transaction.
Fills at the requested limit are fictional and do not model market liquidity.
"""

from decimal import Decimal


class SyntheticExecutionBroker:
    @staticmethod
    def fill(proposal_id, order, current_account):
        quantity = Decimal(order["quantity"])
        delta = quantity if order["side"] == "buy" else -quantity
        account = dict(current_account)
        positions = dict(account["positions"])
        positions[order["symbol"]] = str(Decimal(positions.get(order["symbol"], "0")) + delta)
        account["positions"] = positions
        account["cash"] = str(Decimal(account["cash"]) - delta * Decimal(order["limit_price"]))
        return account, {
            "id": proposal_id,
            "client_order_id": proposal_id,
            "status": "filled",
            "synthetic": True,
            "filled_quantity": str(quantity),
            "fill_price": order["limit_price"],
        }
