"""Generate the preregistered synthetic lab and review artifacts, with no network."""

import argparse
import json
from pathlib import Path

from sqlalchemy import create_engine

from backtesting.storage import ExperimentRegistry
from experiment_lab.fixtures import demonstration_plan
from experiment_lab.reports import markdown
from experiment_lab.service import StrategyExperimentLab
from experiment_lab.storage import LabRegistry


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--database",
        type=Path,
        required=True,
        help="Local registry outside synced/private production storage",
    )
    parser.add_argument(
        "--output", type=Path, required=True, help="Synthetic JSON/Markdown output directory"
    )
    args = parser.parse_args()
    args.database.parent.mkdir(parents=True, exist_ok=True)
    args.output.mkdir(parents=True, exist_ok=True)
    registry = LabRegistry(
        ExperimentRegistry(create_engine("sqlite:///" + args.database.resolve().as_posix()))
    )
    registry.initialize()
    plan, datasets = demonstration_plan()
    # Save the plan artifact before evaluation, mirroring the durable registry reservation.
    (args.output / "plan.json").write_text(plan.model_dump_json(indent=2), encoding="utf-8")
    result = StrategyExperimentLab(registry).run(plan, datasets)
    (args.output / "results.json").write_text(result.model_dump_json(indent=2), encoding="utf-8")
    (args.output / "human-review.md").write_text(markdown(plan, result), encoding="utf-8")
    print(
        json.dumps(
            {
                "label": "SYNTHETIC SOFTWARE ONLY",
                "runs": len(result.results),
                "validation": {r["strategy_id"]: r["paper_eligibility"] for r in result.validation},
                "forward_paper_sessions": 0,
                "production_execution": "DISABLED",
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
