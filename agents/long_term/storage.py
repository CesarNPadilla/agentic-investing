"""Atomic local assessment, thesis-review and audit persistence; no broker access."""

from sqlalchemy import JSON, String, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Mapped, Session, mapped_column

from agents.long_term.models import ResearchAssessment, ResearchRun
from database.repository import Base
from portfolio.storage import PortfolioStore, StoredThesis, ThesisRow
from portfolio.theses import PositionThesis, ThesisReview


class AssessmentRow(Base):
    __tablename__ = "long_term_assessments_v1"
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    scope: Mapped[str] = mapped_column(String(200), index=True)
    symbol: Mapped[str] = mapped_column(String(100), index=True)
    payload: Mapped[dict] = mapped_column(JSON)


class AssessmentHead(Base):
    __tablename__ = "long_term_assessment_heads_v1"
    scope: Mapped[str] = mapped_column(String(200), primary_key=True)
    symbol: Mapped[str] = mapped_column(String(100), primary_key=True)
    assessment_id: Mapped[str] = mapped_column(String(36))


class ResearchRunRow(Base):
    __tablename__ = "long_term_runs_v1"
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    scope: Mapped[str] = mapped_column(String(200), index=True)
    symbol: Mapped[str] = mapped_column(String(100), index=True)
    payload: Mapped[dict] = mapped_column(JSON)


class ResearchEventRow(Base):
    __tablename__ = "long_term_completed_events_v1"
    scope: Mapped[str] = mapped_column(String(200), primary_key=True)
    symbol: Mapped[str] = mapped_column(String(100), primary_key=True)
    event: Mapped[str] = mapped_column(String(200), primary_key=True)
    assessment_id: Mapped[str] = mapped_column(String(36))


class ResearchStore:
    def __init__(self, engine):
        self.engine = engine
        self.portfolio = PortfolioStore(engine)

    def initialize(self):
        # Additive bootstrap only; production migration/backup review is still required.
        Base.metadata.create_all(self.engine)

    def get(self, assessment_id):
        with Session(self.engine) as session:
            row = session.get(AssessmentRow, assessment_id)
            return ResearchAssessment.model_validate(row.payload) if row else None

    def latest(self, scope, symbol):
        with Session(self.engine) as session:
            head = session.get(AssessmentHead, (scope, symbol))
            if not head:
                return None
            return ResearchAssessment.model_validate(
                session.get(AssessmentRow, head.assessment_id).payload
            )

    def history(self, scope, symbol, *, limit=100):
        if not 1 <= limit <= 500:
            raise ValueError("History limit must be between 1 and 500")
        # Follow immutable links, not timestamp sorting (timestamps can tie).
        result, current = [], self.latest(scope, symbol)
        while current is not None and len(result) < limit:
            result.append(current)
            current = (
                self.get(current.previous_assessment_id) if current.previous_assessment_id else None
            )
        return tuple(result)

    def begin(self, run):
        with Session(self.engine) as session, session.begin():
            session.add(
                ResearchRunRow(
                    id=run.run_id,
                    scope=run.scope_id,
                    symbol=run.symbol,
                    payload=run.model_dump(mode="json"),
                )
            )

    def finish(self, run):
        with Session(self.engine) as session, session.begin():
            row = session.get(ResearchRunRow, run.run_id)
            if row is None or row.payload["status"] != "STARTED":
                raise ValueError("Run is not active")
            row.payload = run.model_dump(mode="json")

    def runs(self, scope, symbol):
        with Session(self.engine) as session:
            return tuple(
                ResearchRun.model_validate(r.payload)
                for r in session.scalars(
                    select(ResearchRunRow).where(
                        ResearchRunRow.scope == scope, ResearchRunRow.symbol == symbol
                    )
                )
            )

    def event_completed(self, scope, symbol, event):
        with Session(self.engine) as session:
            return session.get(ResearchEventRow, (scope, symbol, event)) is not None

    def commit(self, assessment, run, theses: tuple[StoredThesis, ...], events=()):
        """CAS on assessment head and thesis revisions; all effects succeed or roll back."""
        try:
            with Session(self.engine) as session, session.begin():
                if assessment.previous_assessment_id is None:
                    session.add(
                        AssessmentHead(
                            scope=assessment.scope_id,
                            symbol=assessment.symbol,
                            assessment_id=assessment.assessment_id,
                        )
                    )
                else:
                    changed = session.execute(
                        update(AssessmentHead)
                        .where(
                            AssessmentHead.scope == assessment.scope_id,
                            AssessmentHead.symbol == assessment.symbol,
                            AssessmentHead.assessment_id == assessment.previous_assessment_id,
                        )
                        .values(assessment_id=assessment.assessment_id)
                    )
                    if changed.rowcount != 1:
                        raise ValueError("Assessment revision conflict")
                session.add(
                    AssessmentRow(
                        id=assessment.assessment_id,
                        scope=assessment.scope_id,
                        symbol=assessment.symbol,
                        payload=assessment.model_dump(mode="json"),
                    )
                )
                for stored in theses:
                    old = stored.thesis
                    latest = session.scalar(
                        select(ThesisRow)
                        .where(
                            ThesisRow.account_id == old.account_id, ThesisRow.symbol == old.symbol
                        )
                        .order_by(ThesisRow.revision.desc())
                        .limit(1)
                    )
                    if latest is None or latest.revision != stored.revision:
                        raise ValueError("Thesis revision conflict")
                    review = ThesisReview(
                        review_id=assessment.assessment_id,
                        agent="long-term-research-v0.1",
                        reviewed_at=assessment.timestamp,
                        assessment=assessment.thesis_status,
                        evidence_references=(f"assessment:{assessment.assessment_id}",),
                    )
                    values = old.model_dump() | {
                        "agent_review_history": (*old.agent_review_history, review),
                        "last_review_date": assessment.timestamp,
                    }
                    if assessment.plan is not None and old.thesis_status != "ARCHIVED":
                        values["current_thesis"] = assessment.plan.thesis
                    if (
                        old.next_scheduled_review
                        and old.next_scheduled_review <= assessment.timestamp
                    ):
                        values["next_scheduled_review"] = None
                    # Lifecycle status is separate from research direction. Never reactivate
                    # an invalidated/archived owner thesis automatically.
                    if old.thesis_status not in {"INVALIDATED", "ARCHIVED"}:
                        if assessment.thesis_status == "INVALIDATED":
                            values["thesis_status"] = "INVALIDATED"
                        elif assessment.thesis_status in {
                            "WEAKER",
                            "UNDER_REVIEW",
                            "INSUFFICIENT_DATA",
                        }:
                            values["thesis_status"] = "REVIEW_REQUIRED"
                    if old.last_review_date and old.last_review_date > assessment.timestamp:
                        raise ValueError("Review date cannot regress")
                    revised = PositionThesis.model_validate(values)
                    session.add(
                        ThesisRow(
                            account_id=old.account_id,
                            symbol=old.symbol,
                            revision=stored.revision + 1,
                            payload=revised.model_dump(mode="json"),
                        )
                    )
                for event in events:
                    session.add(
                        ResearchEventRow(
                            scope=assessment.scope_id,
                            symbol=assessment.symbol,
                            event=event,
                            assessment_id=assessment.assessment_id,
                        )
                    )
                row = session.get(ResearchRunRow, run.run_id)
                if row is None or row.payload["status"] != "STARTED":
                    raise ValueError("Run is not active")
                row.payload = run.model_dump(mode="json")
        except IntegrityError:
            raise ValueError("Research or thesis revision conflict") from None
