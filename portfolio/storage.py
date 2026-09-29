"""Application-database persistence for private read-only broker evidence and theses."""

from uuid import uuid4

from pydantic import Field
from sqlalchemy import JSON, Integer, String, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Mapped, Session, mapped_column

from database.repository import Base
from portfolio.intelligence import PortfolioIntelligence, SecurityReference
from portfolio.state import ExperimentalAttribution, PortfolioState, Reconciliation, Record
from portfolio.theses import PositionThesis


class PortfolioObservation(Record):
    id: str = Field(default_factory=lambda: str(uuid4()))
    opening_id: str | None = None
    state: PortfolioState
    intelligence: PortfolioIntelligence
    reconciliation: Reconciliation | None = None
    reference_data: tuple[SecurityReference, ...] = ()


class AnalysisInput(Record):
    experimental_attribution: ExperimentalAttribution | None = None
    references: tuple[SecurityReference, ...] = ()


class ThesisInput(Record):
    expected_revision: int = Field(ge=0)
    thesis: PositionThesis


class StoredThesis(Record):
    revision: int
    thesis: PositionThesis


class ObservationRow(Base):
    __tablename__ = "portfolio_observations_v3"
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    payload: Mapped[dict] = mapped_column(JSON, nullable=False)


class ThesisRow(Base):
    __tablename__ = "position_theses_v1"
    account_id: Mapped[str] = mapped_column(String(200), primary_key=True)
    symbol: Mapped[str] = mapped_column(String(100), primary_key=True)
    revision: Mapped[int] = mapped_column(Integer, primary_key=True)
    payload: Mapped[dict] = mapped_column(JSON, nullable=False)


class PortfolioStore:
    def __init__(self, engine):
        self.engine = engine

    def save(self, observation: PortfolioObservation):
        with Session(self.engine) as session, session.begin():
            session.add(
                ObservationRow(id=observation.id, payload=observation.model_dump(mode="json"))
            )

    def get(self, observation_id: str):
        with Session(self.engine) as session:
            row = session.get(ObservationRow, observation_id)
            return PortfolioObservation.model_validate(row.payload) if row else None

    def get_thesis(self, account_id: str, symbol: str):
        with Session(self.engine) as session:
            row = session.scalar(
                select(ThesisRow)
                .where(ThesisRow.account_id == account_id, ThesisRow.symbol == symbol)
                .order_by(ThesisRow.revision.desc())
                .limit(1)
            )
            return (
                StoredThesis(
                    revision=row.revision, thesis=PositionThesis.model_validate(row.payload)
                )
                if row
                else None
            )

    def save_thesis(self, request: ThesisInput):
        thesis = request.thesis
        previous = self.get_thesis(thesis.account_id, thesis.symbol)
        if request.expected_revision != (previous.revision if previous else 0):
            raise ValueError("Thesis revision conflict")
        if previous:
            old = previous.thesis
            if old.original_thesis is not None and old.original_thesis != thesis.original_thesis:
                raise ValueError("Original thesis cannot be overwritten")
            if (
                thesis.agent_review_history[: len(old.agent_review_history)]
                != old.agent_review_history
            ):
                raise ValueError("Agent review history is append-only")
            if old.last_review_date and (
                thesis.last_review_date is None or thesis.last_review_date < old.last_review_date
            ):
                raise ValueError("Review date cannot regress")
        revision = request.expected_revision + 1
        try:
            with Session(self.engine) as session, session.begin():
                session.add(
                    ThesisRow(
                        account_id=thesis.account_id,
                        symbol=thesis.symbol,
                        revision=revision,
                        payload=thesis.model_dump(mode="json"),
                    )
                )
        except IntegrityError:
            raise ValueError("Thesis revision conflict") from None
        return StoredThesis(revision=revision, thesis=thesis)
