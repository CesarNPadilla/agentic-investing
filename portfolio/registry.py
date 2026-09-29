"""Owner-supplied v0.2 roles. No invented purchase rationale or broker holdings."""

from decimal import Decimal

from portfolio.theses import PositionThesis

# Missing sleeve assignments intentionally remain unknown; a role is not a numeric target.
REGISTRY = {
    "VOO": {
        "classification": "CORE_LONG_TERM",
        "sleeve": "CORE",
        "portfolio_role": "Diversified broad-market core and primary portfolio benchmark",
    },
    "MSFT": {
        "classification": "STRATEGIC_LONG_TERM",
        "sleeve": "STRATEGIC",
        "portfolio_role": "Magnificent Seven / cloud / enterprise software / AI strategic growth",
    },
    "NVDA": {
        "classification": "STRATEGIC_LONG_TERM",
        "sleeve": "STRATEGIC",
        "portfolio_role": "Magnificent Seven / accelerated computing / AI infrastructure",
    },
    "INTC": {
        "classification": "TURNAROUND_LONG_TERM",
        "risk_flags": ("CONCENTRATION_RISK",),
        "portfolio_role": "Semiconductor manufacturing/foundry/compute turnaround",
    },
    "PLTR": {
        "classification": "STRATEGIC_HIGH_GROWTH",
        "risk_flags": ("CONCENTRATION_RISK",),
        "portfolio_role": "AI software/platform growth",
    },
    "COIN": {
        "classification": "HIGH_RISK_LONG_TERM",
        "secondary_classifications": ("SWING_ELIGIBLE",),
        "portfolio_role": "Crypto infrastructure / financial technology",
    },
    "RIOT": {
        "classification": "HIGH_RISK_THEMATIC",
        "secondary_classifications": ("SWING_ELIGIBLE",),
        "portfolio_role": "Bitcoin infrastructure / mining / data-center optionality",
    },
    "RIVN": {
        "classification": "SPECULATIVE_LONG_TERM",
        "portfolio_role": "EV growth / R2 execution thesis",
    },
    "NIO": {"classification": "SPECULATIVE_THESIS_REVIEW", "portfolio_role": "EV turnaround"},
    "LCID": {
        "classification": "SPECULATIVE_THESIS_REVIEW",
        "portfolio_role": "EV turnaround / technology optionality",
    },
    "GAIN": {
        "classification": "INCOME_DIVERSIFIER",
        "portfolio_role": "Income / BDC diversification",
    },
    "F": {"classification": "LEGACY_POSITION"},
    "GNW": {"classification": "LEGACY_POSITION"},
    "OPK": {"classification": "LEGACY_POSITION"},
}


def initial_thesis(account_id: str, symbol: str, allocation: Decimal | None = None):
    supplied = REGISTRY.get(symbol, {})
    if not supplied and allocation is not None and 0 <= allocation < Decimal("0.005"):
        supplied = {"classification": "LEGACY_POSITION"}
    return PositionThesis(
        account_id=account_id, symbol=symbol, current_allocation=allocation, **supplied
    )
