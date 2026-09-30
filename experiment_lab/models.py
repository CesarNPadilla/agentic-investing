"""Frozen preregistration and explicit study design for exactly two hypotheses."""

from datetime import date
from typing import Literal

from pydantic import AwareDatetime, Field, model_validator

from backtesting.models import BacktestConfig, Period, ValidationGates
from experiment_lab.definitions import LONG_TERM_ID, SWING_ID, sensitivity_definitions
from portfolio.state import Identifier, Record
from risk.evaluator import digest
from strategies.models import StrategyVersion


class DatasetPin(Record):
    dataset_id: Identifier
    version: Identifier
    content_digest: Identifier
    # Common lineage identifies revisions/renames of the same underlying observations.
    lineage: Identifier


class PlannedRun(Record):
    config: BacktestConfig
    dataset: DatasetPin
    purpose: Literal["baseline", "sensitivity"] = "baseline"


class ExperimentPlan(Record):
    schema_version: Literal["strategy-experiment-lab-v1"] = "strategy-experiment-lab-v1"
    plan_id: Identifier
    created_at: AwareDatetime
    hypotheses: tuple[StrategyVersion, ...]
    periods: tuple[Period, ...]
    runs: tuple[PlannedRun, ...] = Field(min_length=1)
    validation_gates: ValidationGates = ValidationGates()
    human_review_required: Literal[True] = True
    optimization_allowed: Literal[False] = False

    @model_validator(mode="after")
    def controlled(self):
        if len(self.hypotheses) != 2 or {v.strategy_id for v in self.hypotheses} != {
            LONG_TERM_ID,
            SWING_ID,
        }:
            raise ValueError("Exactly the two initial hypotheses are required")
        if any(v.strategy_version != "1.0.0" or v.status != "BACKTEST" for v in self.hypotheses):
            raise ValueError("Initial hypotheses are immutable BACKTEST v1.0.0 definitions")
        if {p.role for p in self.periods} != {"development", "validation", "out_of_sample"} or len(
            self.periods
        ) != 3:
            raise ValueError("Separate development/validation/out-of-sample periods required")
        if len({r.config.backtest_id for r in self.runs}) != len(self.runs):
            raise ValueError("Duplicate run ID")
        run_keys = [
            (
                r.config.strategy.strategy_id,
                r.config.strategy.strategy_version,
                r.config.evaluated_role,
                r.config.capital_mode,
            )
            for r in self.runs
        ]
        if len(set(run_keys)) != len(run_keys):
            raise ValueError("Duplicate experiment cell; no capital/parameter grid")
        definitions = {v.strategy_id: v for v in self.hypotheses}
        for run in self.runs:
            config = run.config
            baseline = definitions.get(config.strategy.strategy_id)
            if baseline is None or tuple(config.periods) != tuple(self.periods):
                raise ValueError(
                    "Every run must bind a hypothesis and the complete fixed period plan"
                )
            if not set(config.security_universe) <= set(baseline.experiment.permitted_symbols):
                raise ValueError("Run universe exceeds preregistered strategy universe")
            if config.benchmark != "VOO":
                raise ValueError("Initial experiments require the VOO benchmark")
            if run.purpose == "baseline":
                if digest(config.strategy) != digest(baseline):
                    raise ValueError("Baseline changed without a new version")
            elif config.evaluated_role != "development" or digest(config.strategy) not in {
                digest(v) for v in sensitivity_definitions(baseline)
            }:
                raise ValueError("Sensitivity permits only the predetermined development probes")
            if run.purpose == "sensitivity":
                control = next(
                    (
                        r
                        for r in self.runs
                        if r.purpose == "baseline"
                        and r.config.strategy.strategy_id == config.strategy.strategy_id
                        and r.config.evaluated_role == "development"
                        and r.config.capital_mode == config.capital_mode
                    ),
                    None,
                )
                excluded = {"backtest_id", "strategy"}
                if (
                    control is None
                    or control.dataset != run.dataset
                    or digest(control.config.model_dump(exclude=excluded))
                    != digest(config.model_dump(exclude=excluded))
                ):
                    raise ValueError(
                        "Sensitivity must change one declared rule, with identical data/capital/costs"
                    )
        for baseline in self.hypotheses:
            roles = {
                r.config.evaluated_role
                for r in self.runs
                if r.purpose == "baseline" and r.config.strategy.strategy_id == baseline.strategy_id
            }
            if roles != {"development", "validation", "out_of_sample"}:
                raise ValueError("Every hypothesis requires all three periods")
        sensitivity = [r for r in self.runs if r.purpose == "sensitivity"]
        if len(sensitivity) > 3 or len(
            {r.config.strategy.strategy_version for r in sensitivity}
        ) != len(sensitivity):
            raise ValueError("At most three unique sensitivity probes; no grid or repetitions")
        # No security filtering after seeing a period's performance.
        for baseline in self.hypotheses:
            universes = {
                r.config.security_universe
                for r in self.runs
                if r.config.strategy.strategy_id == baseline.strategy_id
            }
            if len(universes) != 1:
                raise ValueError("Use the same preregistered universe in every period/probe")
            for mode in {
                r.config.capital_mode
                for r in self.runs
                if r.config.strategy.strategy_id == baseline.strategy_id and r.purpose == "baseline"
            }:
                cells = [
                    r.config
                    for r in self.runs
                    if r.config.strategy.strategy_id == baseline.strategy_id
                    and r.purpose == "baseline"
                    and r.config.capital_mode == mode
                ]
                if {c.evaluated_role for c in cells} != {
                    "development",
                    "validation",
                    "out_of_sample",
                }:
                    raise ValueError("Every capital mode needs all three periods")
                excluded = {
                    "backtest_id",
                    "start_date",
                    "end_date",
                    "evaluated_role",
                    "data_source_metadata",
                }
                if len({digest(c.model_dump(exclude=excluded)) for c in cells}) != 1:
                    raise ValueError(
                        "Capital, rules, costs and policy must remain fixed across periods"
                    )
        return self


class DataExposure(Record):
    plan_id: str
    lineage: str
    start: date
    end: date
    symbols: tuple[str, ...]
    role: str
    source_dataset_digest: str
    exposed_at: AwareDatetime


class LabResult(Record):
    plan_id: str
    plan_digest: str
    results: tuple[dict, ...]
    validation: tuple[dict, ...]
    sensitivity: tuple[dict, ...]
    data_exposures: tuple[DataExposure, ...]
    human_review_required: Literal[True] = True
    forward_paper_sessions: Literal[0] = 0
    required_forward_paper_sessions: Literal[60] = 60
    production_execution: Literal["DISABLED"] = "DISABLED"
