"""Offline, staged historical candidate study. No broker or paper entry point."""

import argparse
import json
import sqlite3
from pathlib import Path

from experiment_lab.historical_data import JsonHistoricalResearchProvider
from experiment_lab.historical_research import (
    HistoricalResearchPlan,
    HistoricalResearchStudy,
    robustness_summary,
)
from risk.evaluator import digest


def _write(path, value):
    path.write_text(json.dumps(value, indent=2, default=str) + "\n", encoding="utf-8")


def reserve(database: Path, plan: HistoricalResearchPlan):
    """Durably reserve an OOS security/date exposure before any computation."""
    database.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(database) as connection:
        connection.execute("BEGIN IMMEDIATE")
        connection.execute("""
            CREATE TABLE IF NOT EXISTS historical_research_reservations (
                plan_id TEXT PRIMARY KEY, plan_digest TEXT NOT NULL,
                symbols TEXT NOT NULL, start TEXT NOT NULL, end TEXT NOT NULL,
                oos_start TEXT NOT NULL, oos_end TEXT NOT NULL,
                status TEXT NOT NULL
            )
        """)
        previous = connection.execute(
            "SELECT plan_id, plan_digest, symbols, start, end, oos_start, oos_end "
            "FROM historical_research_reservations"
        ).fetchall()
        for prior_id, prior_digest, symbols, start, end, oos_start, oos_end in previous:
            if prior_id == plan.plan_id:
                if prior_digest != digest(plan):
                    raise ValueError("Immutable historical plan ID conflict")
                raise ValueError("Historical plan already exposed; no repeat or tuning")
            common = set(json.loads(symbols)) & {*plan.symbols, plan.benchmark}
            new_start, new_end = str(plan.periods[0].start), str(plan.periods[-1].end)
            new_oos_start, new_oos_end = str(plan.periods[-1].start), str(plan.periods[-1].end)
            if common and (
                max(oos_start, new_start) <= min(oos_end, new_end)
                or max(new_oos_start, start) <= min(new_oos_end, end)
            ):
                raise ValueError("OOS_CONTAMINATION: overlapping security dates already exposed")
        connection.execute(
            "INSERT INTO historical_research_reservations VALUES (?,?,?,?,?,?,?,?)",
            (plan.plan_id, digest(plan), json.dumps((*plan.symbols, plan.benchmark)),
             str(plan.periods[0].start), str(plan.periods[-1].end),
             str(plan.periods[-1].start), str(plan.periods[-1].end), "RESERVED"),
        )


def _stage(database, plan_id, status):
    with sqlite3.connect(database) as connection:
        connection.execute(
            "UPDATE historical_research_reservations SET status=? WHERE plan_id=?",
            (status, plan_id),
        )


def run(plan_path: Path, data_path: Path, output: Path, registry: Path):
    plan = HistoricalResearchPlan.model_validate_json(plan_path.read_text(encoding="utf-8"))
    dataset = JsonHistoricalResearchProvider(data_path).load(
        json.loads(data_path.read_text(encoding="utf-8"))["dataset_id"],
        json.loads(data_path.read_text(encoding="utf-8"))["version"],
    )
    study = HistoricalResearchStudy(plan, dataset)
    if output.exists() and any(output.iterdir()):
        raise ValueError("Output directory must be empty; previous results are immutable")
    reserve(registry, plan)
    output.mkdir(parents=True, exist_ok=True)
    _write(output / "frozen-plan.json", plan.model_dump(mode="json"))
    try:
        development = study.development()
        _write(output / "development.json", development)
        _write(output / "development-sensitivity.json", study.results["sensitivity"])
        _stage(registry, plan.plan_id, study.phase)
        validation, checks = study.validation()
        _write(output / "validation.json", {"results": validation, "gates": checks,
                                             "realistic_capital_gates":
                                             study.results["experimental_capital_validation_gates"]})
        _write(output / "period-robustness.json", robustness_summary(development, validation))
        _stage(registry, plan.plan_id, study.phase)
        _write(output / "status.json", study.status())
        return study.status()
    except Exception:
        _stage(registry, plan.plan_id, "FAILED_EXPOSURE_RETAINED")
        raise


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--plan", type=Path, required=True)
    parser.add_argument("--dataset", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--registry", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(run(args.plan, args.dataset, args.output, args.registry), indent=2))


if __name__ == "__main__":
    main()
