"""Strict current diagnostic scope; configuration cannot enable execution."""

import json


def selected_symbol(root):
    spec = json.loads((root / "conf/paper-etf-plumbing.json").read_text(encoding="utf-8"))
    if (
        spec.get("strategy_id") != "PAPER_ETF_CONTROL_PLUMBING"
        or spec.get("version") != "1.0.0"
        or spec.get("allowed_symbols") != ["SCHB"]
        or spec.get("disabled_symbols") != ["INTC"]
        or spec.get("instrument_category") != "ETF_ONLY"
        or any(
            spec.get(field) is not False
            for field in ("execution_available", "trial_started", "live_authorized")
        )
    ):
        raise ValueError("ETF diagnostic scope invalid")
    return "SCHB"
