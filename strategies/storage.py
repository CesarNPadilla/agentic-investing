"""Append-only evaluation bundles with atomic opportunities, proposals and audit events."""

from sqlalchemy import JSON, String, select
from sqlalchemy.orm import Mapped, Session, mapped_column

from database.repository import Base
from risk.evaluator import digest
from strategies.models import InvestmentOpportunity, StrategyVersion


class StrategyRow(Base):
    __tablename__ = "opportunity_strategy_versions_v1"
    strategy_id: Mapped[str] = mapped_column(String(200), primary_key=True)
    version: Mapped[str] = mapped_column(String(200), primary_key=True)
    payload: Mapped[dict] = mapped_column(JSON)


class EvaluationRow(Base):
    __tablename__ = "opportunity_evaluations_v1"
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    scope: Mapped[str] = mapped_column(String(200), index=True)
    symbol: Mapped[str] = mapped_column(String(100), index=True)
    payload: Mapped[dict] = mapped_column(JSON)


class StrategyStore:
    def __init__(self, engine):
        self.engine = engine

    def initialize(self):
        Base.metadata.create_all(self.engine)

    def register(self, version: StrategyVersion):
        # Unique key rejects concurrent competing definitions; never overwrite a version.
        with Session(self.engine) as session, session.begin():
            key = (version.strategy_id, version.strategy_version)
            existing = session.get(StrategyRow, key)
            if existing:
                if digest(StrategyVersion.model_validate(existing.payload)) != digest(version):
                    raise ValueError("Strategy version conflict")
            else:
                session.add(
                    StrategyRow(
                        strategy_id=key[0], version=key[1], payload=version.model_dump(mode="json")
                    )
                )

    def version(self, strategy_id, version):
        with Session(self.engine) as session:
            row = session.get(StrategyRow, (strategy_id, version))
            return StrategyVersion.model_validate(row.payload) if row else None

    def save(self, opportunity, bundle):
        with Session(self.engine) as session, session.begin():
            session.add(
                EvaluationRow(
                    id=opportunity.opportunity_id,
                    scope=opportunity.scope_id,
                    symbol=opportunity.symbol,
                    payload=bundle,
                )
            )

    def get(self, opportunity_id):
        with Session(self.engine) as session:
            row = session.get(EvaluationRow, opportunity_id)
            return row.payload if row else None

    def opportunity(self, opportunity_id):
        bundle = self.get(opportunity_id)
        return InvestmentOpportunity.model_validate(bundle["opportunity"]) if bundle else None

    def history(self, scope, symbol, *, limit=100):
        if not 1 <= limit <= 500:
            raise ValueError("Limit must be between 1 and 500")
        with Session(self.engine) as session:
            rows = session.scalars(
                select(EvaluationRow)
                .where(EvaluationRow.scope == scope, EvaluationRow.symbol == symbol)
                .order_by(EvaluationRow.id)
                .limit(limit)
            )
            return tuple(r.payload for r in rows)
