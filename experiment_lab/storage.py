"""Durable preregistration and exposure receipts, sharing ExperimentRegistry's database."""

import json
from datetime import UTC, datetime

from sqlalchemy import Column, Integer, MetaData, String, Table, Text, select

from backtesting.storage import versions
from experiment_lab.models import DataExposure, ExperimentPlan, LabResult
from risk.evaluator import digest

metadata = MetaData()
plans = Table(
    "strategy_lab_plans_v1",
    metadata,
    Column("plan_id", String, primary_key=True),
    Column("fingerprint", String, nullable=False),
    Column("plan", Text, nullable=False),
    Column("exposures", Text, nullable=False),
    Column("status", String, nullable=False),
    Column("result", Text),
    Column("result_digest", String),
    Column("failure", String),
)
mutex = Table(
    "strategy_lab_exposure_lock_v1",
    metadata,
    Column("id", Integer, primary_key=True),
    Column("revision", Integer, nullable=False),
)


def exposures_for(plan, now):
    receipts = {}
    for run in plan.runs:
        c, pin = run.config, run.dataset
        key = (c.start_date, c.end_date, c.security_universe, c.evaluated_role, pin.content_digest)
        receipts[key] = DataExposure(
            plan_id=plan.plan_id,
            lineage=pin.lineage,
            start=c.start_date,
            end=c.end_date,
            symbols=tuple(sorted({*c.security_universe, c.benchmark})),
            role=c.evaluated_role,
            source_dataset_digest=pin.content_digest,
            exposed_at=now,
        )
    return tuple(receipts.values())


class LabRegistry:
    def __init__(self, experiments):
        self.experiments = experiments
        self.engine = experiments.engine

    def initialize(self):
        self.experiments.initialize()
        metadata.create_all(self.engine)
        with self.engine.begin() as connection:
            if connection.execute(select(mutex.c.id)).first() is None:
                connection.execute(mutex.insert().values(id=1, revision=0))

    def reserve(self, plan):
        """Reserve before any strategy run; failed/abandoned runs remain exposed.

        Serializing a write to one lock row closes concurrent check-then-insert races
        for SQLite and PostgreSQL. Initialization is a separate deployment operation.
        """
        plan = ExperimentPlan.model_validate_json(plan.model_dump_json())
        receipts = exposures_for(plan, datetime.now(UTC))
        with self.engine.begin() as connection:
            connection.execute(
                mutex.update().where(mutex.c.id == 1).values(revision=mutex.c.revision + 1)
            )
            prior = list(connection.execute(select(plans)).mappings())
            existing = next((p for p in prior if p["plan_id"] == plan.plan_id), None)
            if existing:
                if existing["fingerprint"] != digest(plan):
                    raise ValueError("Immutable preregistered plan conflict")
                return existing["status"], tuple(
                    DataExposure.model_validate(e) for e in json.loads(existing["exposures"])
                )
            for row in prior:
                for old in (DataExposure.model_validate(e) for e in json.loads(row["exposures"])):
                    for new in receipts:
                        overlap = max(old.start, new.start) <= min(old.end, new.end) and set(
                            old.symbols
                        ).intersection(new.symbols)
                        if overlap and (old.role == "out_of_sample" or new.role == "out_of_sample"):
                            raise ValueError(
                                "OOS_CONTAMINATION: exposed security dates cannot be reused as unseen or tuned"
                            )
            definitions = {digest(run.config.strategy): run.config.strategy for run in plan.runs}
            for version in definitions.values():
                existing_version = (
                    connection.execute(
                        select(versions).where(
                            versions.c.strategy_id == version.strategy_id,
                            versions.c.strategy_version == version.strategy_version,
                        )
                    )
                    .mappings()
                    .first()
                )
                if existing_version and existing_version["content_digest"] != digest(version):
                    raise ValueError("Immutable strategy version conflict")
                if existing_version is None:
                    connection.execute(
                        versions.insert().values(
                            strategy_id=version.strategy_id,
                            strategy_version=version.strategy_version,
                            content_digest=digest(version),
                        )
                    )
            connection.execute(
                plans.insert().values(
                    plan_id=plan.plan_id,
                    fingerprint=digest(plan),
                    plan=plan.model_dump_json(),
                    exposures=json.dumps([e.model_dump(mode="json") for e in receipts]),
                    status="RESERVED",
                )
            )
        return "RESERVED", receipts

    def start(self, plan_id):
        with self.engine.begin() as connection:
            result = connection.execute(
                plans.update()
                .where(plans.c.plan_id == plan_id, plans.c.status == "RESERVED")
                .values(status="RUNNING")
            )
            if result.rowcount != 1:
                raise ValueError(
                    "Plan already running, failed or completed; exposures cannot be reset"
                )

    def finish(self, plan_id, result):
        with self.engine.begin() as connection:
            row = (
                connection.execute(select(plans).where(plans.c.plan_id == plan_id)).mappings().one()
            )
            if (
                row["fingerprint"] != result.plan_digest
                or result.plan_id != plan_id
                or row["status"] != "RUNNING"
            ):
                raise ValueError("Completion does not bind the running plan")
            connection.execute(
                plans.update()
                .where(plans.c.plan_id == plan_id)
                .values(
                    status="COMPLETED",
                    result=result.model_dump_json(),
                    result_digest=digest(result),
                )
            )

    def fail(self, plan_id, reason):
        with self.engine.begin() as connection:
            connection.execute(
                plans.update()
                .where(plans.c.plan_id == plan_id, plans.c.status == "RUNNING")
                .values(status="FAILED", failure=reason)
            )

    def get(self, plan_id):
        with self.engine.connect() as connection:
            row = (
                connection.execute(select(plans).where(plans.c.plan_id == plan_id))
                .mappings()
                .first()
            )
        if row is None:
            return None
        if digest(ExperimentPlan.model_validate_json(row["plan"])) != row["fingerprint"]:
            raise ValueError("Corrupt preregistration")
        return dict(row)

    def result(self, plan_id):
        row = self.get(plan_id)
        if row is None or row["result"] is None:
            return None
        result = LabResult.model_validate_json(row["result"])
        if digest(result) != row["result_digest"] or result.plan_digest != row["fingerprint"]:
            raise ValueError("Corrupt lab results")
        return result
