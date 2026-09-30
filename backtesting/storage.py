"""Atomic immutable local experiment registry; explicit bootstrap, no API exposure."""

from sqlalchemy import Column, MetaData, String, Table, Text, select

from backtesting.models import BacktestResult, StrategyValidationReport
from risk.evaluator import digest

metadata = MetaData()
experiments = Table(
    "backtest_experiments_v1",
    metadata,
    Column("experiment_id", String, primary_key=True),
    Column("content_digest", String, nullable=False),
    Column("bundle", Text, nullable=False),
)
versions = Table(
    "backtest_strategy_versions_v1",
    metadata,
    Column("strategy_id", String, primary_key=True),
    Column("strategy_version", String, primary_key=True),
    Column("content_digest", String, nullable=False),
)


class ExperimentRegistry:
    def __init__(self, engine):
        self.engine = engine

    def initialize(self):
        metadata.create_all(self.engine)

    def save(self, result, dataset, report=None, notes=""):
        import json

        if digest(dataset) != result.dataset_digest:
            raise ValueError("Dataset digest mismatch")
        if report and result.config.backtest_id not in report.backtests_evaluated:
            raise ValueError("Report does not evaluate this experiment")
        bundle = {
            "result": result.model_dump(mode="json"),
            "dataset": dataset.model_dump(mode="json"),
            "report": report.model_dump(mode="json") if report else None,
            "notes": notes,
            "created_at": result.config.created_at.isoformat(),
        }
        fingerprint = digest(bundle)
        with self.engine.begin() as connection:
            version = result.config.strategy
            registered = (
                connection.execute(
                    select(versions).where(
                        versions.c.strategy_id == version.strategy_id,
                        versions.c.strategy_version == version.strategy_version,
                    )
                )
                .mappings()
                .first()
            )
            if registered and registered["content_digest"] != digest(version):
                raise ValueError("Immutable strategy version conflict")
            if not registered:
                connection.execute(
                    versions.insert().values(
                        strategy_id=version.strategy_id,
                        strategy_version=version.strategy_version,
                        content_digest=digest(version),
                    )
                )
            existing = (
                connection.execute(
                    select(experiments).where(
                        experiments.c.experiment_id == result.config.backtest_id
                    )
                )
                .mappings()
                .first()
            )
            if existing:
                if existing["content_digest"] != fingerprint:
                    raise ValueError("Immutable experiment ID conflict")
                return
            connection.execute(
                experiments.insert().values(
                    experiment_id=result.config.backtest_id,
                    content_digest=fingerprint,
                    bundle=json.dumps(bundle, sort_keys=True),
                )
            )

    def get(self, experiment_id):
        import json

        with self.engine.connect() as connection:
            row = (
                connection.execute(
                    select(experiments).where(experiments.c.experiment_id == experiment_id)
                )
                .mappings()
                .first()
            )
        if row is None:
            return None
        bundle = json.loads(row["bundle"])
        if digest(bundle) != row["content_digest"]:
            raise ValueError("Corrupt experiment")
        BacktestResult.model_validate(bundle["result"])
        if bundle["report"]:
            StrategyValidationReport.model_validate(bundle["report"])
        return bundle
