"""Preregister -> reserve exposure -> deterministic replay -> persist -> human review."""

from backtesting.engine import BacktestEngine
from backtesting.validation import validate
from experiment_lab.diagnostics import capital_diagnostics, sensitivity_summary, summarize
from experiment_lab.models import ExperimentPlan, LabResult
from experiment_lab.validation import lab_validation
from risk.evaluator import digest


class StrategyExperimentLab:
    def __init__(self, registry):
        self.registry = registry

    def run(self, plan, datasets):
        plan = ExperimentPlan.model_validate_json(plan.model_dump_json())
        # Content pins are checked before exposure reservation; no strategy evaluation here.
        for run in plan.runs:
            data = datasets.get(run.dataset.content_digest)
            if (
                data is None
                or digest(data) != run.dataset.content_digest
                or (data.dataset_id, data.version) != (run.dataset.dataset_id, run.dataset.version)
            ):
                raise ValueError("Dataset missing or differs from preregistered pin")
            cutoff = max(data.sessions) if data.sessions else None
            if (
                cutoff is None
                or cutoff.date() > run.config.end_date
                or any(
                    item.available_at > cutoff
                    for item in (*data.bars, *data.research, *data.fundamentals, *data.events)
                )
                or any(
                    h.adjustment_known_at > cutoff or any(s > cutoff for s in h.sessions)
                    for h in data.indicator_vintages
                )
            ):
                raise ValueError(
                    "Period datasets must physically exclude later-period observations"
                )
        state, receipts = self.registry.reserve(plan)
        if state == "COMPLETED":
            return self.registry.result(plan.plan_id)
        self.registry.start(plan.plan_id)
        rows, results, verified = [], [], {}
        try:
            # Complete all development baselines and probes before validation, and
            # never evaluate the reserved holdout while development is in flight.
            role_rank = {"development": 0, "validation": 1, "out_of_sample": 2}
            for run in sorted(plan.runs, key=lambda r: role_rank[r.config.evaluated_role]):
                config = run.config
                data = datasets[run.dataset.content_digest]
                result = BacktestEngine().run(config, data)
                replay = BacktestEngine().run(config, data)
                same = result.model_dump_json() == replay.model_dump_json()
                verified[config.backtest_id] = same
                report = validate((result,), plan.validation_gates)
                # Persist unsuccessful/insufficient results unchanged; never tune or retry rules.
                self.registry.experiments.save(
                    result,
                    data,
                    report,
                    notes=f"Preregistered lab plan {plan.plan_id}; purpose={run.purpose}; reproducible={same}",
                )
                results.append(result)
                rows.append(
                    {
                        "backtest_id": config.backtest_id,
                        "strategy_id": config.strategy.strategy_id,
                        "strategy_version": config.strategy.strategy_version,
                        "purpose": run.purpose,
                        "role": config.evaluated_role,
                        "capital_mode": config.capital_mode,
                        "period": {"start": str(config.start_date), "end": str(config.end_date)},
                        "dataset": run.dataset.model_dump(mode="json"),
                        "status": result.status,
                        "metrics": result.metrics,
                        "data_quality": result.data_quality,
                        "bias_warnings": result.bias_warnings,
                        "reproducible": same,
                        "assumptions": config.execution.model_dump(mode="json"),
                        "diagnostics": summarize(result),
                        "capital_analysis": capital_diagnostics(config, data, result),
                        "result_digest": digest(result),
                        "validation": report.model_dump(mode="json"),
                    }
                )
            reports = []
            for version in plan.hypotheses:
                # Development measures are reported, but cannot serve as validation evidence.
                evidence = tuple(
                    r
                    for r in results
                    if r.config.strategy == version and r.config.evaluated_role != "development"
                )
                reports.append(
                    lab_validation(
                        evidence,
                        plan.validation_gates,
                        reproducible=all(verified[r.config.backtest_id] for r in evidence),
                        fresh_oos=any(e.role == "out_of_sample" for e in receipts),
                    ).model_dump(mode="json")
                )
            lab = LabResult(
                plan_id=plan.plan_id,
                plan_digest=digest(plan),
                results=tuple(rows),
                validation=tuple(reports),
                sensitivity=sensitivity_summary(rows),
                data_exposures=receipts,
            )
            lab = LabResult.model_validate_json(lab.model_dump_json())
            self.registry.finish(plan.plan_id, lab)
            return lab
        except Exception as error:
            self.registry.fail(plan.plan_id, type(error).__name__)
            raise
