"""Application-database persistence for private read-only broker evidence and theses."""

from uuid import uuid4

from pydantic import Field
from sqlalchemy import JSON, Integer, String, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Mapped, Session, mapped_column

from database.repository import Base
from portfolio.intelligence import CorrelationEvidence, PortfolioIntelligence, SecurityReference
from portfolio.performance import PerformanceEvidence
from portfolio.registry import initial_thesis
from portfolio.state import ExperimentalAttribution, PortfolioState, Reconciliation, Record
from portfolio.theses import PositionThesis
from risk.policy import InvestmentPolicy


class PortfolioObservation(Record):
    id: str = Field(default_factory=lambda: str(uuid4()))
    opening_id: str | None = None
    derived_from_id: str | None = None
    policy: InvestmentPolicy
    state: PortfolioState
    intelligence: PortfolioIntelligence
    reconciliation: Reconciliation | None = None
    reference_data: tuple[SecurityReference, ...] = ()
    theses: tuple[PositionThesis, ...] = ()
    correlation_evidence: tuple[CorrelationEvidence, ...] = ()
    performance_evidence: PerformanceEvidence | None = None


class AnalysisInput(Record):
    experimental_attribution: ExperimentalAttribution | None = None
    references: tuple[SecurityReference, ...] = ()
    correlations: tuple[CorrelationEvidence, ...] = ()
    performance_evidence: PerformanceEvidence | None = None

    def resolve(self, previous: PortfolioObservation):
        """Omitted fields inherit; explicit null/empty values clear prior evidence."""
        baseline = {
            "experimental_attribution": previous.state.experimental_attribution,
            "references": previous.reference_data,
            "correlations": previous.correlation_evidence,
            "performance_evidence": previous.performance_evidence,
        }
        return AnalysisInput.model_validate(baseline | self.model_dump(exclude_unset=True))


class ThesisInput(Record):
    expected_revision: int = Field(ge=0)
    thesis: PositionThesis


class StoredThesis(Record):
    revision: int
    thesis: PositionThesis


class ObservationRow(Base):
    __tablename__ = "portfolio_observations_v4"
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    payload: Mapped[dict] = mapped_column(JSON, nullable=False)


class ThesisRow(Base):
    __tablename__ = "position_theses_v1"
    account_id: Mapped[str] = mapped_column(String(200), primary_key=True)
    symbol: Mapped[str] = mapped_column(String(100), primary_key=True)
    revision: Mapped[int] = mapped_column(Integer, primary_key=True)
    payload: Mapped[dict] = mapped_column(JSON, nullable=False)


class ReviewRequestRow(Base):
    __tablename__ = "thesis_review_requests_v1"
    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    payload: Mapped[dict] = mapped_column(JSON, nullable=False)


class RiskReviewRow(Base):
    __tablename__ = "proposal_risk_reviews_v1"
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
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
            if thesis.material_events[: len(old.material_events)] != old.material_events:
                raise ValueError("Material event history is append-only")
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

    def thesis_history(self, account_id: str, symbol: str, after_revision: int, limit: int):
        with Session(self.engine) as session:
            rows = session.scalars(
                select(ThesisRow)
                .where(
                    ThesisRow.account_id == account_id,
                    ThesisRow.symbol == symbol,
                    ThesisRow.revision > after_revision,
                )
                .order_by(ThesisRow.revision)
                .limit(limit)
            )
            return tuple(
                StoredThesis(
                    revision=row.revision, thesis=PositionThesis.model_validate(row.payload)
                )
                for row in rows
            )

    def initialize_theses(self, state: PortfolioState):
        values = [p.marked_value for p in state.positions]
        cash = [a.cash for a in state.accounts]
        known = (
            state.accounts_complete
            and state.positions_complete
            and all(a.currency == "USD" for a in state.accounts)
            and all(p.currency == "USD" for p in state.positions)
            and all(v is not None for v in (*values, *cash))
        )
        total = sum(values) + sum(cash) if known else None
        result = []
        for position in state.portfolio_holdings:
            current = self.get_thesis(position.account_id, position.symbol)
            if current is None:
                allocation = (
                    abs(position.marked_value) / total if total is not None and total > 0 else None
                )
                initial = initial_thesis(position.account_id, position.symbol, allocation)
                try:
                    current = self.save_thesis(ThesisInput(expected_revision=0, thesis=initial))
                except ValueError:
                    current = self.get_thesis(position.account_id, position.symbol)
                    if current is None:
                        raise
            result.append(current.thesis)
        return tuple(result)

    def save_review_requests(self, requests, evidence=None):
        for request in requests:
            try:
                with Session(self.engine) as session, session.begin():
                    if session.get(ReviewRequestRow, request.request_id) is None:
                        session.add(
                            ReviewRequestRow(
                                id=request.request_id,
                                payload={
                                    "request": request.model_dump(mode="json"),
                                    "untrusted_evidence": evidence.model_dump(mode="json")
                                    if evidence
                                    else None,
                                },
                            )
                        )
            except IntegrityError:
                # A competing insert may win; the first immutable request is retained.
                with Session(self.engine) as session:
                    if session.get(ReviewRequestRow, request.request_id) is None:
                        raise

    def review_requests(self, state):
        from news.thesis_review import ThesisReviewRequest

        keys = {(p.account_id, p.symbol) for p in state.portfolio_holdings}
        with Session(self.engine) as session:
            requests = [
                ThesisReviewRequest.model_validate(row.payload["request"])
                for row in session.scalars(select(ReviewRequestRow))
            ]
        return tuple(
            sorted(
                (r for r in requests if (r.account_id, r.symbol) in keys),
                key=lambda r: (r.requested_at, r.request_id),
            )
        )

    def save_risk_review(
        self, review, policy, opening_id, closing_id, thesis, validation, kill_switch
    ):
        identifier = str(uuid4())
        with Session(self.engine) as session, session.begin():
            session.add(
                RiskReviewRow(
                    id=identifier,
                    payload={
                        "review": review.model_dump(mode="json"),
                        "policy": policy.model_dump(mode="json"),
                        "opening_id": opening_id,
                        "closing_id": closing_id,
                        "thesis": thesis.model_dump(mode="json") if thesis else None,
                        "validation": validation.model_dump(mode="json") if validation else None,
                        "kill_switch": kill_switch.model_dump(mode="json"),
                    },
                )
            )
        return identifier

    def get_risk_review(self, identifier):
        with Session(self.engine) as session:
            row = session.get(RiskReviewRow, identifier)
            return row.payload if row else None
