"""Read-only SEC accession coverage report for the sealed historical study."""

import argparse
import json
import os
from collections import Counter
from datetime import UTC, date, datetime
from pathlib import Path

from experiment_lab.knowledge_boundary import HistoricalKnowledgeBoundary, KnowledgeObservation
from experiment_lab.sec_edgar_historical import SecEdgarHistoricalFundamentalProvider

PINNED_CIKS = {
    "AAPL": 320193, "MSFT": 789019, "NVDA": 1045810, "AMZN": 1018724,
    "GOOGL": 1652044, "GOOG": 1652044, "META": 1326801,
    "TSLA": 1318605, "PLTR": 1321655, "INTC": 50863,
}


def summarize(provider: SecEdgarHistoricalFundamentalProvider,
              *, through: date = date(2025, 12, 31)) -> dict:
    if through > date(2025, 12, 31):
        raise ValueError("Reserved OOS period may not be inspected")
    at = datetime.combine(through, datetime.max.time(), tzinfo=UTC)
    summary = {}
    unique = set()
    for symbol, cik in PINNED_CIKS.items():
        rows = provider.statements(symbol, through=through, since=date(2023, 1, 1))
        unique.update((cik, row.source_reference) for row in rows)
        boundary = HistoricalKnowledgeBoundary()
        states = Counter(boundary.classify(KnowledgeObservation(
            "fundamental", row.source_reference, row.accepted_at, row.revision_proven,
        ), at).value for row in rows)
        summary[symbol] = {
            "filings": len(rows), "annual": sum(row.fiscal_period == "FY" for row in rows),
            "quarterly": sum(row.fiscal_period == "QUARTER" for row in rows),
            "amendments": sum(row.amendment_indicator is not None for row in rows),
            "acceptance_timestamp_count": sum(row.accepted_at is not None for row in rows),
            "accession_provenance_count": sum(bool(row.provider_metadata["fact_provenance"])
                                              for row in rows),
            "metrics": dict(sorted(Counter(metric for row in rows
                                           for metric in row.normalized_values).items())),
            "knowledge_states": dict(states),
        }
    return {"scope": "DEVELOPMENT_VALIDATION_ONLY", "through": through.isoformat(),
            "summary": summary, "unique_cik_accessions": len(unique),
            "oos_results_exposed": False, "research_only": True}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--through", type=date.fromisoformat,
                        default=date(2025, 12, 31))
    args = parser.parse_args()
    if args.output.exists():
        raise ValueError("SEC qualification report already exists")
    user_agent = os.environ.get("SEC_USER_AGENT", "")
    provider = SecEdgarHistoricalFundamentalProvider(user_agent, PINNED_CIKS)
    report = summarize(provider, through=args.through)
    args.output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print("SEC qualification coverage written; holdout remains sealed")


if __name__ == "__main__":
    main()
