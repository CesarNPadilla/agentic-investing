"""Text-only boundary; no tool, broker, filesystem, or execution capabilities."""

from typing import Protocol

from reports.models import ResearchReport


class ResearchSynthesizer(Protocol):
    def summarize(self, report: ResearchReport) -> str: ...


# No LLM implementation is enabled. External content must remain untrusted evidence.
