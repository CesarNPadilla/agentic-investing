"""Conservative derived research metrics from accepted, versioned filings only."""

from datetime import datetime
from decimal import Decimal

from experiment_lab.historical_records import HistoricalStatement
from experiment_lab.knowledge_boundary import HistoricalKnowledgeBoundary, KnowledgeObservation


def reconstruct_quality_metrics(
    statements: tuple[HistoricalStatement, ...], at: datetime,
    boundary: HistoricalKnowledgeBoundary,
) -> dict:
    """Use only proven annual versions and report every unresolved dimension.

    Current SEC companyfacts-derived statements carry revision_proven=False,
    so this function correctly returns no qualifying metrics for live v0.3 data.
    """
    known = []
    for row in statements:
        if boundary.require(KnowledgeObservation(
            "fundamental", row.source_reference or row.raw_payload_digest,
            row.accepted_at, row.revision_proven,
        ), at):
            known.append(row)
    annual = [row for row in known if row.fiscal_period == "FY" and row.currency == "USD"]
    # An amendment supersedes the original only after its own acceptance, and
    # only when that amendment's revision provenance is established.
    by_period = {}
    for row in sorted(annual, key=lambda item: item.accepted_at):
        by_period[row.period_end] = row
    ordered = sorted(by_period.values(), key=lambda item: item.period_end)
    metrics = {}
    if ordered:
        current = ordered[-1].normalized_values
        previous = ordered[-2].normalized_values if len(ordered) >= 2 else {}
        for name, source in (("revenue_growth", "revenue"),
                             ("earnings_growth", "net_income")):
            if source in current and source in previous and previous[source] != 0:
                metrics[name] = current[source] / previous[source] - 1
        if "operating_cash_flow" in current and "capital_expenditure" in current:
            metrics["free_cash_flow"] = (current["operating_cash_flow"]
                                         - current["capital_expenditure"])
        for name, numerator in (("gross_margin", "gross_profit"),
                                ("operating_margin", "operating_income"),
                                ("net_margin", "net_income")):
            if numerator in current and current.get("revenue", Decimal(0)) > 0:
                metrics[name] = current[numerator] / current["revenue"]
        if all(key in current for key in ("debt_current", "debt_noncurrent", "cash")):
            metrics["total_debt"] = current["debt_current"] + current["debt_noncurrent"]
            metrics["net_debt"] = metrics["total_debt"] - current["cash"]
        if "net_income" in current and current.get("assets", Decimal(0)) > 0:
            metrics["return_on_assets"] = current["net_income"] / current["assets"]
    required = (
        "revenue_growth", "earnings_growth", "free_cash_flow", "gross_margin",
        "operating_margin", "net_margin", "total_debt", "net_debt",
        "return_on_assets", "net_debt_to_ebitda", "free_cash_flow_yield",
        "growth_durability", "valuation_context", "thesis_state", "portfolio_fit",
    )
    return {"metrics": metrics,
            "missing": tuple(name for name in required if name not in metrics),
            "qualifying": len(metrics) == len(required),
            "source_accessions": tuple(row.source_reference for row in ordered)}
