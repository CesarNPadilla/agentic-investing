"""Owner-authored position theses and append-only agent review history."""

from itertools import pairwise
from typing import Annotated

from pydantic import AwareDatetime, Field, model_validator

from market_data.models import Symbol
from portfolio.state import Identifier, Nonnegative, Record


class ThesisReview(Record):
    review_id: Identifier
    agent: Identifier
    reviewed_at: AwareDatetime
    assessment: Identifier
    evidence_references: tuple[str, ...] = ()


class PositionThesis(Record):
    account_id: Identifier
    symbol: Symbol
    reason_for_ownership: str | None = None
    original_thesis: str | None = None
    current_thesis: str | None = None
    expected_catalysts: tuple[str, ...] | None = None
    risks: tuple[str, ...] | None = None
    invalidation_conditions: tuple[str, ...] | None = None
    target_allocation: Annotated[Nonnegative, Field(le=1)] | None = None
    last_review_date: AwareDatetime | None = None
    agent_review_history: tuple[ThesisReview, ...] = ()

    @model_validator(mode="after")
    def ordered_reviews(self):
        reviews = self.agent_review_history
        if len({r.review_id for r in reviews}) != len(reviews):
            raise ValueError("Duplicate review ID")
        if any(a.reviewed_at > b.reviewed_at for a, b in pairwise(reviews)):
            raise ValueError("Review history must be chronological")
        if reviews and (
            self.last_review_date is None or self.last_review_date < reviews[-1].reviewed_at
        ):
            raise ValueError("Last review date must include latest agent review")
        return self
