"""Provider-neutral valuation, preserving separate methods, bases, and periods."""

from typing import Protocol

from agents.long_term.models import Claim, Metric, ValuationContext


class ValuationAnalyzer(Protocol):
    def analyze(self, metrics: tuple[Metric, ...]) -> ValuationContext: ...


class ReportedValuation:
    def __init__(self, methods=None):
        self.methods = frozenset(
            methods
            if methods is not None
            else (
                "pe",
                "forward_pe",
                "price_sales",
                "ev_revenue",
                "ev_ebitda",
                "fcf_yield",
                "growth_adjusted_valuation",
                "historical_valuation_low",
                "historical_valuation_high",
                "peer_valuation_median",
            )
        )

    def analyze(self, metrics):
        selected = tuple(m for m in metrics if m.name in self.methods)
        return ValuationContext(
            status="AVAILABLE" if selected else "INSUFFICIENT_DATA",
            methods=selected,
            conclusions=tuple(
                Claim(
                    text=f"Reported {m.name}: {m.value} {m.unit}; {m.basis}; period {m.period_end}",
                    evidence_references=(m.source_id,),
                    kind="fact",
                )
                for m in selected
            ),
        )
