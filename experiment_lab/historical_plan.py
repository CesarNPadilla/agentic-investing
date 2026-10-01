"""Freeze historical research rules and gates before any strategy result is calculated."""

import argparse
import hashlib
from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path

from backtesting.models import Period, ValidationGates
from experiment_lab.historical_data import HistoricalResearchDataset
from experiment_lab.historical_research import HistoricalResearchPlan, ResearchRules


def code_version():
    root = Path(__file__).resolve().parents[1]
    source_hash = hashlib.sha256()
    for path in sorted((root / "experiment_lab").glob("*.py")):
        source_hash.update(path.name.encode())
        source_hash.update(path.read_bytes().replace(b"\r\n", b"\n"))
    return "historical-research-sha256:" + source_hash.hexdigest()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--dataset", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--plan-id", required=True)
    parser.add_argument("--symbols", required=True, help="Comma-separated fixed security universe")
    for name in ("development-start", "development-end", "validation-start",
                 "validation-end", "oos-start", "oos-end"):
        parser.add_argument("--" + name, type=date.fromisoformat, required=True)
    args = parser.parse_args()
    dataset = HistoricalResearchDataset.model_validate_json(
        args.dataset.read_text(encoding="utf-8")
    )
    if args.output.exists():
        raise ValueError("Refusing to overwrite a frozen plan")
    periods = (
        Period(role="development", start=args.development_start, end=args.development_end),
        Period(role="validation", start=args.validation_start, end=args.validation_end),
        Period(role="out_of_sample", start=args.oos_start, end=args.oos_end),
    )
    plan = HistoricalResearchPlan(
        plan_id=args.plan_id, created_at=datetime.now(UTC),
        dataset_digest=dataset.content_digest,
        symbols=tuple(s.strip().upper() for s in args.symbols.split(",") if s.strip()),
        periods=periods, rules=ResearchRules(),
        gates=ValidationGates(
            minimum_observations=126, minimum_trades=5,
            max_drawdown=Decimal("0.25"), max_turnover=Decimal(3),
            acceptable_data_quality=(), zero_lookahead_violations=True,
            zero_policy_bypasses=True,
        ),
        source_version=code_version(),
    )
    args.output.write_text(plan.model_dump_json(indent=2) + "\n", encoding="utf-8")
    print(f"Frozen plan written: {args.output}")


if __name__ == "__main__":
    main()
