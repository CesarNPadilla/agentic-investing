"""Describe an existing validation ledger without changing strategy rules."""

import json
from collections import Counter
from datetime import datetime
from decimal import Decimal
from pathlib import Path
from statistics import mean, median


def diagnose(row: dict) -> dict:
    if (row.get("role"), row.get("strategy_id"), row.get("capital")) != (
        "validation", "SWING_TREND_MOMENTUM", "100000"
    ):
        raise ValueError("Only the exposed normalized 2025 swing validation ledger is accepted")
    trades = row["trades"]
    sessions = [datetime.fromisoformat(p["session"]) for p in row["curve"]]
    session_index = {session: index for index, session in enumerate(sessions)}
    entries, exits, reasons = Counter(), Counter(), Counter()
    open_entries = {}
    holding, reentry = [], []
    last_exit = {}
    paired = 0
    notional = Decimal(0)
    for trade in trades:
        symbol = trade["symbol"]
        at = datetime.fromisoformat(trade["filled_at"])
        notional += Decimal(trade["quantity"]) * Decimal(trade["price"])
        if trade["side"] == "buy":
            entries[symbol] += 1
            if symbol in last_exit:
                reentry.append(session_index[at] - session_index[last_exit[symbol]])
            if symbol in open_entries:
                raise ValueError("Overlapping same-symbol entry")
            open_entries[symbol] = at
        elif trade["side"] == "sell":
            exits[symbol] += 1
            reasons[trade["reason"]] += 1
            if symbol not in open_entries:
                raise ValueError("Exit without entry")
            holding.append(session_index[at] - session_index[open_entries.pop(symbol)])
            last_exit[symbol] = at
            paired += 1
        else:
            raise ValueError("Unexpected side")
    return {
        "entries_per_symbol": dict(sorted(entries.items())),
        "exits_per_symbol": dict(sorted(exits.items())),
        "exit_reasons": dict(sorted(reasons.items())),
        "completed_round_trips": paired,
        "open_positions_at_period_end": len(open_entries),
        "holding_sessions": {"average": mean(holding), "median": median(holding),
                             "shortest": min(holding), "longest": max(holding)},
        "same_symbol_reentries": len(reentry),
        "exit_to_reentry_sessions": {"average": mean(reentry), "median": median(reentry),
                                     "shortest": min(reentry), "longest": max(reentry)},
        "maximum_simultaneous_positions": row["metrics"]["maximum_simultaneous_positions"],
        "end_cash_utilization": row["metrics"]["cash_utilization"],
        "fees": row["metrics"]["fees"],
        "estimated_slippage_cost": str(notional * Decimal("0.0005")),
        "estimated_half_spread_cost": str(notional * Decimal("0.0001")),
        "turnover": row["metrics"]["turnover"],
        "unavailable_from_ledger": [
            "signal_gate_transitions", "rejected_candidate_proposals", "risk_engine_decisions",
            "session_cash_utilization", "exact_execution_shortfall",
        ],
        "research_only": True,
        "rules_unchanged": True,
    }


def diagnose_file(path: Path) -> dict:
    payload = json.loads(path.read_text(encoding="utf-8"))
    rows = payload["results"]
    if any(row.get("role") != "validation" for row in rows):
        raise ValueError("Non-validation rows are forbidden")
    return diagnose(next(row for row in rows if row["strategy_id"] == "SWING_TREND_MOMENTUM"
                         and row["capital"] == "100000"))
