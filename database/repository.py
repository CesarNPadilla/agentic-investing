from typing import Protocol
from uuid import UUID

from sqlalchemy import JSON, Integer, String, create_engine, text, update
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column

from reports.models import ResearchReport
from simulation.models import SimulationRun


class ReportRepository(Protocol):
    def save(self, report: ResearchReport) -> None: ...
    def get(self, report_id: UUID) -> ResearchReport | None: ...


class Base(DeclarativeBase):
    pass


class ReportRow(Base):
    __tablename__ = "research_reports"
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    payload: Mapped[dict] = mapped_column(JSON, nullable=False)


class SimulationRow(Base):
    __tablename__ = "simulation_runs"
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    revision: Mapped[int] = mapped_column(Integer, nullable=False)
    payload: Mapped[dict] = mapped_column(JSON, nullable=False)


class SQLReportRepository:
    def __init__(self, url: str):
        self.engine = create_engine(url, pool_pre_ping=True)

    def initialize(self) -> None:
        # Bootstrap only. Use versioned migrations before evolving this schema.
        Base.metadata.create_all(self.engine)

    def ready(self) -> None:
        with self.engine.connect() as connection:
            connection.execute(text("SELECT 1"))

    def save(self, report: ResearchReport) -> None:
        with Session(self.engine) as session, session.begin():
            session.add(ReportRow(id=str(report.id), payload=report.model_dump(mode="json")))

    def get(self, report_id: UUID) -> ResearchReport | None:
        with Session(self.engine) as session:
            row = session.get(ReportRow, str(report_id))
            return ResearchReport.model_validate(row.payload) if row else None

    def close(self) -> None:
        self.engine.dispose()

    def save_simulation(self, run: SimulationRun, expected_revision: int | None = None) -> bool:
        with Session(self.engine) as session, session.begin():
            payload = run.model_dump(mode="json")
            if expected_revision is None:
                session.add(SimulationRow(id=str(run.id), revision=run.revision, payload=payload))
                return True
            result = session.execute(
                update(SimulationRow)
                .where(SimulationRow.id == str(run.id), SimulationRow.revision == expected_revision)
                .values(revision=run.revision, payload=payload)
            )
            return result.rowcount == 1

    def get_simulation(self, run_id: UUID) -> SimulationRun | None:
        with Session(self.engine) as session:
            row = session.get(SimulationRow, str(run_id))
            return SimulationRun.model_validate(row.payload) if row else None
