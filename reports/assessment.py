from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class ResearchObservation(BaseModel):
    model_config = ConfigDict(extra="forbid")
    direction: Literal["supporting", "counter", "neutral"]
    statement: str
    evidence_refs: list[str]


class ResearchAssessment(BaseModel):
    model_config = ConfigDict(extra="forbid")
    method: Literal["deterministic-v1"] = "deterministic-v1"
    conclusion: str
    observations: list[ResearchObservation] = Field(default_factory=list)
    review_questions: list[str] = Field(default_factory=list)
    limitations: list[str] = Field(default_factory=list)
