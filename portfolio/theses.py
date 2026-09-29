"""Owner-authored position theses and append-only agent review history."""

from itertools import pairwise
from typing import Annotated, Literal

from pydantic import AwareDatetime, ConfigDict, Field, model_validator

from market_data.models import Symbol
from portfolio.state import Identifier, Nonnegative, Record
from risk.policy import AllocationRange

Classification = Literal[
    "CORE_LONG_TERM",
    "STRATEGIC_LONG_TERM",
    "TURNAROUND_LONG_TERM",
    "STRATEGIC_HIGH_GROWTH",
    "HIGH_RISK_LONG_TERM",
    "HIGH_RISK_THEMATIC",
    "SPECULATIVE_LONG_TERM",
    "SPECULATIVE_THESIS_REVIEW",
    "INCOME_DIVERSIFIER",
    "LEGACY_POSITION",
    "UNCLASSIFIED",
]


class MaterialEvent(Record):
    event_id: Identifier
    occurred_at: AwareDatetime
    category: str
    source_reference: Identifier
    summary: Identifier


class ThesisReview(Record):
    review_id: Identifier
    agent: Identifier
    reviewed_at: AwareDatetime
    assessment: Identifier
    evidence_references: tuple[str, ...] = ()


class PositionThesis(Record):
    model_config = ConfigDict(frozen=True, extra="forbid", populate_by_name=True)
    account_id: Identifier
    symbol: Symbol
    portfolio_role: str | None = None
    classification: Classification = "UNCLASSIFIED"
    secondary_classifications: tuple[Literal["SWING_ELIGIBLE"], ...] = ()
    risk_flags: tuple[Literal["CONCENTRATION_RISK"], ...] = ()
    sleeve: Literal["CORE", "STRATEGIC", "SATELLITE"] | None = None
    strategy_domain: Literal["long_term", "swing"] | None = None
    thesis_status: Literal["UNKNOWN", "ACTIVE", "REVIEW_REQUIRED", "INVALIDATED", "ARCHIVED"] = (
        "UNKNOWN"
    )
    original_thesis_status: Literal["UNKNOWN", "SUPPLIED"] = "UNKNOWN"
    reason_for_ownership: str | None = None
    original_thesis: str | None = None
    current_thesis: str | None = None
    expected_catalysts: tuple[str, ...] | None = None
    fundamental_drivers: tuple[str, ...] | None = None
    risks: tuple[str, ...] | None = Field(default=None, alias="primary_risks")
    invalidation_conditions: tuple[str, ...] | None = Field(
        default=None, alias="thesis_invalidation_conditions"
    )
    target_allocation: Annotated[Nonnegative, Field(le=1)] | None = None
    target_allocation_range: AllocationRange | None = None
    current_allocation: Nonnegative | None = None
    conviction_level: Literal["LOW", "MEDIUM", "HIGH"] | None = None
    investment_horizon: str | None = None
    benchmark: str | None = "VOO / S&P 500"
    last_review_date: AwareDatetime | None = None
    next_scheduled_review: AwareDatetime | None = None
    material_events: tuple[MaterialEvent, ...] = ()
    agent_review_history: tuple[ThesisReview, ...] = Field(default=(), alias="agent_reviews")
    human_notes: tuple[str, ...] | None = None

    @model_validator(mode="after")
    def ordered_reviews(self):
        if self.original_thesis is not None:
            if not self.original_thesis.strip():
                raise ValueError("Original thesis cannot be blank")
            object.__setattr__(self, "original_thesis_status", "SUPPLIED")
        elif self.original_thesis_status != "UNKNOWN":
            raise ValueError("Missing historical rationale must remain UNKNOWN")
        if (
            self.next_scheduled_review is not None
            and self.last_review_date is not None
            and self.next_scheduled_review <= self.last_review_date
        ):
            raise ValueError("Next review must follow last review")
        if (
            self.target_allocation is not None
            and self.target_allocation_range is not None
            and not self.target_allocation_range.minimum
            <= self.target_allocation
            <= self.target_allocation_range.maximum
        ):
            raise ValueError("Target allocation conflicts with range")
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
