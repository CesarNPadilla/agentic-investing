"""Research-only historical information availability checks.

An observation is never admitted merely because its economic period predates a
simulation. Provider revision provenance is independent of publication time.
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum
from typing import Literal


class KnowledgeState(StrEnum):
    KNOWN = "KNOWN"
    NOT_YET_KNOWN = "NOT_YET_KNOWN"
    UNCERTAIN = "UNCERTAIN"
    UNAVAILABLE = "UNAVAILABLE"


KnowledgeKind = Literal[
    "fundamental", "corporate_action", "research_event", "valuation_input",
    "symbol_change", "price_bar",
]


@dataclass(frozen=True)
class KnowledgeObservation:
    kind: KnowledgeKind
    reference: str
    available_at: datetime | None
    revision_proven: bool
    present: bool = True


@dataclass
class HistoricalKnowledgeBoundary:
    exclusions: list[dict[str, str]] = field(default_factory=list)

    def classify(self, observation: KnowledgeObservation, at: datetime) -> KnowledgeState:
        if at.tzinfo is None:
            raise ValueError("Simulation timestamp must include a timezone")
        if not observation.present:
            state = KnowledgeState.UNAVAILABLE
        elif observation.available_at is None or observation.available_at.tzinfo is None:
            state = KnowledgeState.UNCERTAIN
        elif observation.available_at > at:
            state = KnowledgeState.NOT_YET_KNOWN
        elif not observation.revision_proven:
            state = KnowledgeState.UNCERTAIN
        else:
            state = KnowledgeState.KNOWN
        if state != KnowledgeState.KNOWN:
            self.exclusions.append({
                "kind": observation.kind, "reference": observation.reference,
                "simulation_at": at.isoformat(), "state": state.value,
            })
        return state

    def require(self, observation: KnowledgeObservation, at: datetime) -> bool:
        return self.classify(observation, at) == KnowledgeState.KNOWN
