"""Isolated retrospective diagnostics; never a qualifying or execution workflow."""

import hashlib
import json
import math
import statistics
from collections import Counter, defaultdict
from datetime import UTC, date, datetime
from decimal import Decimal
from enum import StrEnum
from itertools import pairwise
from pathlib import Path

from backtesting.models import Period, ValidationGates
from experiment_lab.corporate_action_reconstruction import LedgerEvent, account_returns
from experiment_lab.definitions import LONG_TERM_ID, SWING_ID, initial_definitions
from experiment_lab.historical_data import HistoricalResearchDataset
from experiment_lab.historical_plan import code_version
from experiment_lab.historical_records import RawHistoricalPriceBar
from experiment_lab.historical_research import HistoricalResearchPlan, ResearchRules, simulate
from risk.evaluator import digest

CUTOFF = date(2025, 12, 31)
DEVELOPMENT = Period(role="development", start=date(2023, 1, 3), end=date(2024, 12, 31))
VALIDATION = Period(role="validation", start=date(2025, 1, 2), end=CUTOFF)
# Metadata only; this role is never passed to simulate or a data provider.
SEALED_OOS = Period(role="out_of_sample", start=date(2026, 1, 2),
                    end=date(2026, 9, 29))
EXPECTED_DEFINITION_DIGESTS = {
    LONG_TERM_ID: "34ed9e50b475b56a74c2f5f029d37bd7f9ea303e29844339cc3e3e566b460278",
    SWING_ID: "9b5016895d65789100aabb9a98a7f3269876e33a04fbdf3ef495759c3fd5e77d",
}


class ResearchEvidenceClass(StrEnum):
    SOFTWARE_FIXTURE = "SOFTWARE_FIXTURE"
    EXPLORATORY_RETROSPECTIVE = "EXPLORATORY_RETROSPECTIVE"
    QUALIFYING_HISTORICAL = "QUALIFYING_HISTORICAL"
    FORWARD_PAPER = "FORWARD_PAPER"


def _hash(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def _load_bounded(path: Path, *, kind: str) -> tuple[dict, str]:
    raw = path.read_bytes()
    value = json.loads(raw)
    if kind == "dataset":
        if any(datetime.fromisoformat(s).date() > CUTOFF for s in value["sessions"]):
            raise ValueError("2026 OOS dataset refused")
        if any(datetime.fromisoformat(b["session_close"]).date() > CUTOFF
               for b in value["bars"]):
            raise ValueError("2026 OOS bar refused")
        if any(datetime.fromisoformat(f["period_end"]).date() > CUTOFF or
               datetime.fromisoformat(f["published_at"]).date() > CUTOFF
               for f in value.get("fundamentals", ())):
            raise ValueError("2026 OOS fundamental refused")
    elif kind == "raw":
        if any(datetime.fromisoformat(b["timestamp"]).date() > CUTOFF
               for b in value["bars"]):
            raise ValueError("2026 OOS raw bar refused")
    elif kind == "actions":
        if any(any(date.fromisoformat(e[field]) > CUTOFF for field in
                   ("ex_date", "effective_date", "payment_date") if e.get(field))
               for e in value["events"]):
            raise ValueError("2026 OOS action refused")
    return value, _hash(raw)


def _statistics(row: dict, dataset: HistoricalResearchDataset, period: Period) -> dict:
    trades, curve = row["trades"], row["curve"]
    changes = [float(Decimal(b["equity"]) / Decimal(a["equity"]) - 1)
               for a, b in pairwise(curve)]
    volatility = statistics.pstdev(changes) * math.sqrt(252) if len(changes) >= 2 else None
    downside = [min(value, 0.0) for value in changes]
    downside_volatility = (math.sqrt(sum(value * value for value in downside) / len(downside))
                           * math.sqrt(252) if downside else None)
    annual_mean = statistics.mean(changes) * 252 if changes else None
    sharpe = annual_mean / volatility if volatility and len(changes) >= 30 else None
    sortino = (annual_mean / downside_volatility
               if downside_volatility and len(changes) >= 30 else None)
    sessions = [datetime.fromisoformat(point["session"]) for point in curve]
    index = {session: i for i, session in enumerate(sessions)}
    open_by_symbol, prior_exit = {}, {}
    pnl, holding, reentries, reentry_by_exit = [], [], [], Counter()
    reentry_buy_turnover = Decimal(0)
    holding_exit_turnover = Decimal(0)
    reentry_technicals = []
    signal_by_key = {(s["symbol"], s["side"], s["session"]): s
                     for s in row.get("candidate_signals", ())}
    by_symbol = defaultdict(lambda: {"buys": 0, "sells": 0, "turnover": Decimal(0),
                                 "friction": Decimal(0), "exit_reasons": Counter(),
                                 "reentries": 0})
    mark = {(bar.symbol, bar.session_close): bar.close for bar in dataset.bars
            if period.start <= bar.session_close.date() <= period.end}
    capital = Decimal(row["capital"])
    friction = Decimal(0)
    for trade in trades:
        symbol = trade["symbol"]
        side = trade["side"]
        fill = datetime.fromisoformat(trade["filled_at"])
        price, quantity = Decimal(trade["price"]), Decimal(trade["quantity"])
        cost = abs(price - mark[symbol, fill]) * quantity + Decimal("0.10")
        friction += cost
        stats = by_symbol[symbol]
        stats["friction"] += cost
        stats["turnover"] += price * quantity / capital
        stats["buys" if side == "buy" else "sells"] += 1
        if side == "buy":
            if symbol in prior_exit:
                lag = index[fill] - index[prior_exit[symbol][0]]
                reentries.append(lag)
                reentry_by_exit[prior_exit[symbol][1]] += 1
                stats["reentries"] += 1
                reentry_buy_turnover += price * quantity / capital
                signal = signal_by_key.get((symbol, side, trade["signal"]))
                reentry_technicals.append({"symbol": symbol, "prior_exit":
                                           prior_exit[symbol][1], "lag_sessions": lag,
                                           "technical": signal["technical"] if signal else None})
            open_by_symbol[symbol] = (price, quantity, fill)
        else:
            stats["exit_reasons"][trade["reason"]] += 1
            if trade["reason"] == "HOLDING_LIMIT":
                holding_exit_turnover += price * quantity / capital
            if symbol in open_by_symbol:
                entry_price, entry_quantity, entered = open_by_symbol.pop(symbol)
                pnl.append((price - entry_price) * min(quantity, entry_quantity)
                           - Decimal("0.20"))
                holding.append(index[fill] - index[entered])
            prior_exit[symbol] = (fill, trade["reason"])
    winners = [value for value in pnl if value > 0]
    losers = [value for value in pnl if value < 0]
    exposure = [Decimal(point["exposure"]) for point in curve
                if point.get("exposure") is not None]
    reasons = Counter(trade["reason"] for trade in trades if trade["side"] == "sell")
    entries = Counter(signal["symbol"] for signal in row.get("candidate_signals", ())
                      if signal["side"] == "buy")
    return {
        "volatility_annualized": volatility, "downside_volatility_annualized":
            downside_volatility, "sharpe_zero_risk_free": sharpe,
        "sortino_zero_target": sortino, "completed_round_trips": len(pnl),
        "win_rate": len(winners) / len(pnl) if pnl else None,
        "average_winner_usd": str(sum(winners) / len(winners)) if winners else None,
        "average_loser_usd": str(sum(losers) / len(losers)) if losers else None,
        "profit_factor": (str(sum(winners) / -sum(losers)) if losers else None),
        "average_holding_sessions": statistics.mean(holding) if holding else None,
        "median_holding_sessions": statistics.median(holding) if holding else None,
        "shortest_holding_sessions": min(holding) if holding else None,
        "longest_holding_sessions": max(holding) if holding else None,
        "same_symbol_reentries": len(reentries),
        "average_sessions_before_reentry": statistics.mean(reentries) if reentries else None,
        "reentries_by_prior_exit_reason": dict(reentry_by_exit),
        "reentry_buy_turnover": str(reentry_buy_turnover),
        "holding_limit_exit_turnover": str(holding_exit_turnover),
        "reentry_technical_snapshots": reentry_technicals,
        "exit_reasons": dict(reasons), "entry_triggers_by_symbol": dict(entries),
        "average_exposure": str(sum(exposure) / len(exposure)) if exposure else None,
        "maximum_exposure": str(max(exposure)) if exposure else None,
        "average_cash_utilization": str(sum(exposure) / len(exposure)) if exposure else None,
        "direct_execution_friction_usd": str(friction),
        "direct_execution_friction_fraction_of_start": str(friction / capital),
        "slippage_and_half_spread_bps_assumed": "6",
        "rejected_proposals": "NOT_APPLICABLE_NO_TRADE_PROPOSAL_OR_RISK_ENGINE",
        "risk_engine_outcomes": "NOT_EXERCISED_COUNTERFACTUAL_ONLY",
        "skipped_whole_share_orders": len(row.get("skipped_orders", ())),
        "per_symbol": {symbol: {
            **{key: value for key, value in values.items()
               if key not in {"turnover", "friction", "exit_reasons"}},
            "turnover": str(values["turnover"]), "friction_usd": str(values["friction"]),
            "exit_reasons": dict(values["exit_reasons"]),
        } for symbol, values in sorted(by_symbol.items())},
    }


def _benchmark_context(raw_data: dict, ledger: dict, period: Period) -> dict:
    bars = tuple(RawHistoricalPriceBar.model_validate(item) for item in raw_data["bars"]
                 if item["symbol"] == "VOO"
                 and period.start <= datetime.fromisoformat(item["timestamp"]).date() <= period.end)
    events = []
    for item in ledger["events"]:
        if item["source_symbol"] != "VOO" or not period.start <= date.fromisoformat(
                item["ex_date"]) <= period.end:
            continue
        # This override permits a diagnostic arithmetic estimate only. The source
        # terms and full action coverage remain unqualified in the actual ledger.
        converted = {**item, "terms_verified": True}
        for name in ("declaration_date", "ex_date", "record_date", "payment_date",
                     "effective_date"):
            if converted[name] is not None:
                converted[name] = date.fromisoformat(converted[name])
        for name in ("publication_at", "retrieved_at"):
            if converted[name] is not None:
                converted[name] = datetime.fromisoformat(converted[name])
        for name in ("amount", "ratio"):
            if converted[name] is not None:
                converted[name] = Decimal(converted[name])
        events.append(LedgerEvent(**converted))
    if len(bars) < 2:
        return {"status": "INSUFFICIENT_DATA", "reason": "VOO_RAW_BARS_MISSING"}
    accounting = account_returns(bars, tuple(events), coverage_complete=True)
    if accounting["status"] == "INSUFFICIENT_DATA":
        return {"status": "INSUFFICIENT_DATA", "reason": accounting["reason"]}
    return {"status": "EXPLORATORY_ESTIMATE_ONLY",
            "raw_price_return": accounting["price_return"],
            "raw_price_plus_cash_dividends_return": accounting["total_return"],
            "dividend_events": len(events),
            "assumptions": ["LEDGER_TERMS_ASSUMED_FOR_ARITHMETIC_ONLY",
                            "ACTION_COVERAGE_ASSUMED_FOR_ARITHMETIC_ONLY",
                            "CASH_DIVIDENDS_NOT_REINVESTED",
                            "CURRENT_VINTAGE_RETROSPECTIVE_SOURCES"]}


class ExploratoryResearchRunner:
    def __init__(self, dataset_path: Path, raw_path: Path, ledger_path: Path):
        self.dataset_path = dataset_path
        self.raw_path = raw_path
        self.ledger_path = ledger_path

    def run(self, experiment_id: str, output: Path | None, *,
            periods: tuple[Period, Period] = (DEVELOPMENT, VALIDATION)) -> dict:
        if (periods != (DEVELOPMENT, VALIDATION) or any(p.end > CUTOFF for p in periods)
                or not experiment_id or (output is not None and output.exists())):
            raise ValueError("Only new, fixed development/validation exploratory runs allowed")
        raw_data, raw_digest = _load_bounded(self.raw_path, kind="raw")
        ledger, ledger_digest = _load_bounded(self.ledger_path, kind="actions")
        data_json, file_digest = _load_bounded(self.dataset_path, kind="dataset")
        dataset = HistoricalResearchDataset.model_validate(data_json)
        if not dataset.sessions or dataset.sessions[-1].date() > CUTOFF:
            raise ValueError("2026 OOS dataset refused")
        if raw_data.get("holdout_exposed") or ledger.get("oos_exposed"):
            raise ValueError("Input holdout exposure")
        definitions = {s.strategy_id: s for s in initial_definitions()}
        if {key: digest(value) for key, value in definitions.items()} != EXPECTED_DEFINITION_DIGESTS:
            raise ValueError("Frozen strategy definitions changed")
        rules = ResearchRules()
        swing = definitions[SWING_ID]
        if (swing.swing.fast_period != rules.swing_fast_sessions
                or swing.swing.slow_period != rules.swing_slow_sessions
                or swing.experiment.rsi_period != rules.swing_rsi_sessions
                or swing.experiment.rsi_lower != rules.swing_rsi_lower
                or swing.experiment.rsi_upper != rules.swing_rsi_upper
                or swing.experiment.volume_period != rules.swing_volume_sessions
                or swing.experiment.atr_period != rules.swing_atr_sessions
                or swing.experiment.atr_stop_multiple != rules.swing_stop_atr_multiple
                or swing.experiment.max_holding_sessions != rules.swing_max_holding_sessions):
            raise ValueError("Swing replay rules differ from frozen v1.0.0")
        plan = HistoricalResearchPlan(
            plan_id=experiment_id, created_at=datetime.now(UTC),
            dataset_digest=dataset.content_digest,
            symbols=("AAPL", "MSFT", "NVDA", "AMZN", "GOOGL", "GOOG", "META",
                     "TSLA", "PLTR", "INTC"),
            periods=(DEVELOPMENT, VALIDATION, SEALED_OOS), rules=rules,
            gates=ValidationGates(minimum_observations=126, minimum_trades=5,
                                  max_drawdown=Decimal("0.25"), max_turnover=Decimal(3),
                                  acceptable_data_quality=(), zero_lookahead_violations=True,
                                  zero_policy_bypasses=True),
            source_version=code_version(),
        )
        rows = []
        for period in periods:
            benchmark_context = _benchmark_context(raw_data, ledger, period)
            for capital in (Decimal(100000), Decimal(160)):
                row = simulate(dataset, plan, period, SWING_ID, capital)
                if row["status"] != "COMPLETED":
                    raise ValueError("Exploratory input incomplete")
                row["extended_diagnostics"] = _statistics(row, dataset, period)
                row["evidence_class"] = ResearchEvidenceClass.EXPLORATORY_RETROSPECTIVE
                row["paper_eligibility"] = "NEVER_FROM_THIS_RESULT"
                row["production_eligibility"] = "NEVER_FROM_THIS_RESULT"
                row["forward_paper_sessions"] = 0
                row["oos_accessed"] = False
                row["benchmark_methodology"] = (
                    "VOO_ALPACA_ADJUSTMENT_ALL_CURRENT_VINTAGE_TOTAL_RETURN_PROXY")
                row["benchmark_context"] = benchmark_context
                rows.append(row)
        result = {"experiment_id": experiment_id,
                  "evidence_class": ResearchEvidenceClass.EXPLORATORY_RETROSPECTIVE,
                  "results": rows, "qualifying_validation": "NOT_RUN",
                  "paper_eligibility": "NEVER_FROM_THIS_RESULT",
                  "production_eligibility": "NEVER_FROM_THIS_RESULT",
                  "forward_paper_sessions": 0, "oos_accessed": False,
                  "benchmark_methodology":
                      "VOO_ALPACA_ADJUSTMENT_ALL_CURRENT_VINTAGE_TOTAL_RETURN_PROXY",
                  "data_limitations": ["IEX_SINGLE_VENUE", "CURRENT_VINTAGE_ADJUSTMENTS",
                                       "CORPORATE_ACTION_COVERAGE_UNVERIFIED",
                                       "SEC_FUNDAMENTAL_PUBLICATION_UNPROVEN",
                                       "RETROSPECTIVE_STRATEGY_DEFINITION",
                                       "SURVIVORSHIP_CONDITIONAL_ON_SELECTED_SECURITIES"],
                  "long_term_status": "EXPLORATORY_RUN_NOT_POSSIBLE_INSUFFICIENT_DATA"}
        canonical = json.dumps(result, sort_keys=True, separators=(",", ":"), default=str).encode()
        manifest = {
            "experiment_id": experiment_id,
            "evidence_class": ResearchEvidenceClass.EXPLORATORY_RETROSPECTIVE,
            "strategy_id": SWING_ID, "strategy_version": "1.0.0",
            "strategy_definition_digest": EXPECTED_DEFINITION_DIGESTS[SWING_ID],
            "long_term_definition_digest": EXPECTED_DEFINITION_DIGESTS[LONG_TERM_ID],
            "code_revision": code_version(), "configuration_digest": digest(rules),
            "dataset_digest": dataset.content_digest, "dataset_file_sha256": file_digest,
            "raw_price_sha256": raw_digest, "corporate_action_ledger_sha256": ledger_digest,
            "benchmark_methodology": result["benchmark_methodology"],
            "periods": [{"role": p.role, "start": str(p.start), "end": str(p.end)}
                        for p in periods], "symbols": plan.symbols, "benchmark": "VOO",
            "execution": {"timing": "next_session_close", "commission_fixed": "0.10",
                          "slippage_bps": "5", "spread_bps": "2", "fractional": False,
                          "cash": "no_borrowing", "dividend":
                              "ALPACA_ADJUSTMENT_ALL_PROXY_NO_SEPARATE_CASH"},
            "random_seed": None, "numerical_tolerance": "exact canonical JSON",
            "result_digest": _hash(canonical), "created_at": datetime.now(UTC).isoformat(),
            "oos_accessed": False, "paper_eligibility": "NEVER_FROM_THIS_RESULT",
            "production_eligibility": "NEVER_FROM_THIS_RESULT",
        }
        if output is not None:
            output.mkdir(parents=True, exist_ok=False)
            (output / "result.json").write_text(json.dumps(result, indent=2, default=str) + "\n")
            (output / "manifest.json").write_text(json.dumps(manifest, indent=2, default=str) + "\n")
        return {"manifest": manifest, "result": result}
