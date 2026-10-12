"""ETF fixture intent contract; inherited real broker mutation prohibition."""

from typing import Literal

from integrations.brokers.alpaca_paper_orders import PaperOrderIntent


class PaperETFOrderIntent(PaperOrderIntent):
    symbol: Literal["SCHB"] = "SCHB"
