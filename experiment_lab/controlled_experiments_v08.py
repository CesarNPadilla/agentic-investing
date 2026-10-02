"""Preregistered, nonqualifying v0.8 counterfactual experiments; no broker access."""

import hashlib
import json
from collections import Counter
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path

from backtesting.models import ValidationGates
from experiment_lab.definitions import SWING_ID, initial_definitions
from experiment_lab.exploratory_sandbox import (
    DEVELOPMENT,
    EXPECTED_DEFINITION_DIGESTS,
    SEALED_OOS,
    VALIDATION,
    ResearchEvidenceClass,
    _load_bounded,
    _statistics,
)
from experiment_lab.historical_data import HistoricalResearchDataset
from experiment_lab.historical_plan import code_version
from experiment_lab.historical_research import HistoricalResearchPlan, ResearchRules, simulate
from risk.evaluator import digest
from risk.policy import InvestmentPolicy

BENCHMARK = "VOO_ALPACA_ADJUSTMENT_ALL_CURRENT_VINTAGE_TOTAL_RETURN_PROXY"
BASELINE_DIGEST = "30f79857dfd68eca48af178cb6cf04f446988c6c3d20e3945fddd6d66c4f7311"
SYMBOLS = ("AAPL", "MSFT", "NVDA", "AMZN", "GOOGL", "GOOG", "META", "TSLA", "PLTR", "INTC")
SCENARIOS = (
    ("NO_COST_MATCHED_COUNTERFACTUAL", Decimal(0), Decimal(0), Decimal(0)),
    ("BASELINE", Decimal("0.10"), Decimal(2), Decimal(5)),
    ("STRESSED", Decimal("0.25"), Decimal(4), Decimal(10)),
)


def _sha(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _canonical(value: dict) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), default=str).encode()


def _exposure_decomposition(row: dict) -> dict:
    records = row.get("exposure_audit", ())
    overlap = Counter()
    for record in records:
        overlap.update(record["constraints"])
    by_session = Counter(record["session"] for record in records
                         if record.get("original_entry_eligible"))
    eligible_sessions = len({point["session"] for point in row["curve"][:-1]})
    return {
        "observed_symbol_sessions": len(records),
        "sessions_with_original_entry_eligibility": len(by_session),
        "sessions_without_original_entry_eligibility": eligible_sessions - len(by_session),
        "original_eligible_symbol_sessions": sum(by_session.values()),
        "maximum_eligible_symbols_in_session": max(by_session.values(), default=0),
        "constraint_counts_overlapping": dict(overlap),
        "constraints_may_overlap": True,
        "simulated_fill_count": len(row["trades"]),
        "pending_order_fills_or_skips": len(row["trades"]) + len(row["skipped_orders"]),
        "risk_engine_outcomes": "NOT_EXERCISED",
        "hypothetical_allocation_only": True,
    }


class ControlledExploratoryV08:
    def __init__(self, dataset_path: Path, raw_path: Path, ledger_path: Path,
                 prereg_root: Path, baseline_full_result: Path):
        self.dataset_path = dataset_path
        self.raw_path = raw_path
        self.ledger_path = ledger_path
        self.prereg_root = prereg_root
        self.baseline_full_result = baseline_full_result

    def preflight(self) -> dict:
        protocol = json.loads((self.prereg_root / "experimental-protocol.json").read_text())
        capital_plan = json.loads((self.prereg_root / "capital-feasibility-plan.json").read_text())
        candidates = json.loads((self.prereg_root / "candidate-specifications.json").read_text())
        registry = json.loads((self.prereg_root / "hypothesis-registry.json").read_text())
        if (protocol["candidate_backtests_run"] != 0 or registry["candidate_backtests_run"] != 0
                or protocol["periods"][-1]["interpretation"] != "SEALED_NO_ACCESS"
                or capital_plan["status"] != "PREREGISTERED_NOT_RUN"
                or capital_plan["proposed_feasibility_capital_usd"] != "1000"):
            raise ValueError("Preregistration changed or OOS unsealed")
        observed = tuple((s["id"], Decimal(s["commission_usd"]),
                          Decimal(s["spread_bps_full"]), Decimal(s["slippage_bps"]))
                         for s in protocol["h04_cost_scenarios"])
        if observed != SCENARIOS or tuple((p["start"], p["end"]) for p in
                                  protocol["periods"][:2]) != (
                                      (str(DEVELOPMENT.start), str(DEVELOPMENT.end)),
                                      (str(VALIDATION.start), str(VALIDATION.end))):
            raise ValueError("Frozen scenarios or periods changed")
        if {c["id"] for c in candidates["candidates"]} != {
                "SWING_REENTRY_RESET_CANDIDATE", "SWING_HOLDING_EXIT_CANDIDATE"}:
            raise ValueError("Candidate registry changed")
        if (candidates["candidates"][1]["id"] != "SWING_HOLDING_EXIT_CANDIDATE"
                or InvestmentPolicy().agent_experimental_capital_limit != 160):
            raise ValueError("Deferred H02 or current policy cap changed")
        definitions = {s.strategy_id: s for s in initial_definitions()}
        if {key: digest(value) for key, value in definitions.items()} != EXPECTED_DEFINITION_DIGESTS:
            raise ValueError("Frozen strategies changed")
        baseline_manifest = json.loads((self.prereg_root.parent /
                                        "exploratory-retrospective-v06" /
                                        "manifest.json").read_text())
        baseline = json.loads(self.baseline_full_result.read_bytes())
        if (_sha(_canonical(baseline)) != BASELINE_DIGEST
                or baseline_manifest["result_digest"] != BASELINE_DIGEST):
            raise ValueError("Locked v0.6 baseline digest mismatch")
        data, dataset_file_digest = _load_bounded(self.dataset_path, kind="dataset")
        raw, raw_digest = _load_bounded(self.raw_path, kind="raw")
        ledger, ledger_digest = _load_bounded(self.ledger_path, kind="actions")
        if raw.get("holdout_exposed") or ledger.get("oos_exposed"):
            raise ValueError("Input holdout exposure")
        dataset = HistoricalResearchDataset.model_validate(data)
        if (dataset.content_digest != protocol["dataset_digest"]
                or dataset_file_digest != protocol["dataset_file_sha256"]
                or raw_digest != baseline_manifest["raw_price_sha256"]
                or ledger_digest != baseline_manifest["corporate_action_ledger_sha256"]):
            raise ValueError("Frozen source digest mismatch")
        rules = ResearchRules()
        if digest(rules) != baseline_manifest["configuration_digest"]:
            raise ValueError("Frozen research rules changed")
        plan = HistoricalResearchPlan(
            plan_id="controlled-v08", created_at=datetime.now(UTC),
            dataset_digest=dataset.content_digest, symbols=SYMBOLS,
            periods=(DEVELOPMENT, VALIDATION, SEALED_OOS), rules=rules,
            gates=ValidationGates(minimum_observations=126, minimum_trades=5,
                                  max_drawdown=Decimal("0.25"), max_turnover=Decimal(3),
                                  acceptable_data_quality=(), zero_lookahead_violations=True,
                                  zero_policy_bypasses=True), source_version=code_version())
        return {"dataset": dataset, "plan": plan, "baseline": baseline,
                "candidate_digest": digest(candidates["candidates"][0]),
                "prereg_digests": {name: _sha((self.prereg_root / name).read_bytes()) for name in
                                    ("hypothesis-registry.json", "candidate-specifications.json",
                                     "experimental-protocol.json", "comparison-metrics.json",
                                     "capital-feasibility-plan.json")},
                "source_digests": {"dataset": dataset.content_digest,
                                   "dataset_file": dataset_file_digest, "raw": raw_digest,
                                   "corporate_actions": ledger_digest}}

    def run(self, output_root: Path | None = None) -> dict:
        if output_root is not None and output_root.exists():
            raise ValueError("Immutable output directory already exists")
        frozen = self.preflight()
        dataset, plan = frozen["dataset"], frozen["plan"]
        outputs = {}

        def cell(period, capital, rules=plan.rules, *, h01=False, h03=False, feasibility=False):
            changed_plan = plan.model_copy(update={"rules": rules})
            row = simulate(dataset, changed_plan, period, SWING_ID, capital,
                           reentry_reset=h01, exposure_diagnostics=h03,
                           feasibility_capital=capital if feasibility else None)
            if row["status"] != "COMPLETED":
                raise ValueError("Incomplete exploratory cell")
            row["extended_diagnostics"] = _statistics(
                row, dataset, period, rules.commission,
                rules.slippage_bps + rules.spread_bps / 2)
            row.update({"evidence_class": ResearchEvidenceClass.EXPLORATORY_RETROSPECTIVE,
                        "benchmark_classification": "EXPLORATORY_NONQUALIFYING_BENCHMARK",
                        "benchmark_methodology": BENCHMARK,
                        "paper_eligibility": "NEVER_FROM_THIS_RESULT",
                        "production_eligibility": "NEVER_FROM_THIS_RESULT",
                        "forward_paper_sessions": 0, "oos_accessed": False})
            return row

        outputs["H01"] = {"rows": [cell(p, Decimal(100000), h01=True, h03=True)
                                    for p in (DEVELOPMENT, VALIDATION)],
                          "hypothesis_id": "H01", "candidate_id":
                          "SWING_REENTRY_RESET_CANDIDATE"}
        baseline_validation = cell(VALIDATION, Decimal(100000), h03=True)
        locked = next(r for r in frozen["baseline"]["results"] if
                      r["role"] == "validation" and r["capital"] == "100000")
        if (list(baseline_validation["trades"]) != locked["trades"]
                or baseline_validation["metrics"] != locked["metrics"]):
            raise ValueError("H03 instrumentation changed baseline fills or metrics")
        outputs["H03"] = {"rows": [baseline_validation], "hypothesis_id": "H03",
                          "exposure_decomposition": _exposure_decomposition(baseline_validation)}
        h04 = []
        for name, commission, spread, slippage in SCENARIOS:
            rules = plan.rules.model_copy(update={"commission": commission,
                                                  "spread_bps": spread,
                                                  "slippage_bps": slippage})
            for period in (DEVELOPMENT, VALIDATION):
                row = cell(period, Decimal(100000), rules)
                row["scenario"] = name
                row["cost_assumptions"] = {"commission_usd": str(commission),
                                           "full_spread_bps": str(spread),
                                           "slippage_bps": str(slippage)}
                h04.append(row)
        outputs["H04"] = {"rows": h04, "hypothesis_id": "H04",
                          "scenario_selection": "NONE_ALL_PREREGISTERED_SCENARIOS_REPORTED"}
        outputs["CAPITAL_1000"] = {
            "rows": [cell(p, Decimal(1000), h03=True, feasibility=True)
                     for p in (DEVELOPMENT, VALIDATION)],
            "hypothesis_id": "CAPITAL_FEASIBILITY", "purpose": "CAPITAL_FEASIBILITY_EXPLORATORY"}
        results = {}
        for key, content in outputs.items():
            experiment_id = f"exploratory-v08-{key.lower()}-fixed"
            result = {"experiment_id": experiment_id,
                      "evidence_class": ResearchEvidenceClass.EXPLORATORY_RETROSPECTIVE,
                      "strategy_id": SWING_ID, "strategy_version": "1.0.0",
                      "parent_definition_digest": EXPECTED_DEFINITION_DIGESTS[SWING_ID],
                      "research_informed_2025": True, "oos_accessed": False,
                      "qualifying_validation": "BLOCKED_NOT_RUN",
                      "paper_eligibility": "NEVER_FROM_THIS_RESULT",
                      "production_eligibility": "NEVER_FROM_THIS_RESULT",
                      "forward_paper_sessions": 0, "execution_available": False,
                      "benchmark_methodology": BENCHMARK,
                      "benchmark_classification": "EXPLORATORY_NONQUALIFYING_BENCHMARK",
                      "limitations": ["CURRENT_VINTAGE_ADJUSTMENTS", "IEX_SINGLE_VENUE",
                                      "CORPORATE_ACTION_COVERAGE_UNVERIFIED",
                                      "SELECTED_SECURITIES_SURVIVORSHIP",
                                      "2025_RESEARCH_INFORMED_NOT_FRESH_HOLDOUT"], **content}
            manifest = {"experiment_id": experiment_id,
                        "evidence_class": ResearchEvidenceClass.EXPLORATORY_RETROSPECTIVE,
                        "hypothesis_id": content["hypothesis_id"],
                        "parent_strategy_id": SWING_ID, "parent_strategy_version": "1.0.0",
                        "candidate_configuration_digest": frozen["candidate_digest"] if key == "H01"
                        else None, "code_revision": code_version(),
                        "source_digests": frozen["source_digests"],
                        "preregistration_digests": frozen["prereg_digests"],
                        "benchmark_methodology": BENCHMARK,
                        "research_periods": [p.model_dump(mode="json") for p in
                                             (DEVELOPMENT, VALIDATION)],
                        "universe": SYMBOLS,
                        "starting_capital": "1000" if key == "CAPITAL_1000" else "100000",
                        "execution": {"timing": "next_session_close", "whole_shares": True,
                                      "cash": "no_borrowing", "dividends":
                                      "adjustment_all_proxy_no_separate_cash"},
                        "cost_scenarios": [r["cost_assumptions"] for r in h04[::2]]
                        if key == "H04" else [{"commission_usd": "0.10",
                                               "full_spread_bps": "2", "slippage_bps": "5"}],
                        "result_digest": _sha(_canonical(result)),
                        "created_at": datetime.now(UTC).isoformat(),
                        "limitations": result["limitations"],
                        "oos_accessed": False,
                        "paper_eligibility": "NEVER_FROM_THIS_RESULT",
                        "production_eligibility": "NEVER_FROM_THIS_RESULT"}
            results[key] = {"result": result, "manifest": manifest}
        if output_root is not None:
            output_root.mkdir(parents=True, exist_ok=False)
            for key, item in results.items():
                target = output_root / item["manifest"]["experiment_id"]
                target.mkdir()
                (target / "manifest.json").write_text(
                    json.dumps(item["manifest"], indent=2, default=str) + "\n")
                (target / "result.json").write_text(
                    json.dumps(item["result"], indent=2, default=str) + "\n")
        return results
