"""Accession-scoped EDGAR reconstruction, amendments, and PIT exclusions."""

from datetime import UTC, date, datetime

import httpx
import pytest

from experiment_lab.knowledge_boundary import (
    HistoricalKnowledgeBoundary,
    KnowledgeObservation,
    KnowledgeState,
)
from experiment_lab.sec_edgar_historical import (
    SecEdgarHistoricalFundamentalProvider,
    reconstruct_statements,
)
from experiment_lab.sec_fundamental_reconstruction import reconstruct_quality_metrics
from experiment_lab.sec_qualify import summarize

CIK = 320193
ORIGINAL = "0000320193-24-000001"
AMENDED = "0000320193-25-000002"


def samples():
    submissions = {"cik": CIK, "filings": {"recent": {
        "accessionNumber": [ORIGINAL, AMENDED, "0000320193-26-000003"],
        "filingDate": ["2024-11-01", "2025-01-10", "2026-01-10"],
        "reportDate": ["2024-09-30", "2024-09-30", "2025-09-30"],
        "acceptanceDateTime": ["2024-11-01T21:00:00.000Z",
                               "2025-01-10T21:00:00.000Z", "2026-01-10T21:00:00.000Z"],
        "form": ["10-K", "10-K/A", "10-K"],
    }}}
    def fact(accn, value, form, filed, end="2024-09-30"):
        return {"accn": accn, "form": form, "filed": filed,
                "start": "2023-10-01", "end": end, "val": value}
    companyfacts = {"cik": CIK, "facts": {"us-gaap": {
        "RevenueFromContractWithCustomerExcludingAssessedTax": {"units": {"USD": [
            fact(ORIGINAL, 100, "10-K", "2024-11-01"),
            fact(AMENDED, 110, "10-K/A", "2025-01-10"),
            fact("0000320193-26-000003", 500, "10-K", "2026-01-10", "2025-09-30"),
        ]}},
        "NetIncomeLoss": {"units": {"USD": [
            fact(ORIGINAL, 20, "10-K", "2024-11-01"),
            fact(AMENDED, 22, "10-K/A", "2025-01-10"),
        ]}},
    }}}
    return submissions, companyfacts


def test_amendment_is_separate_accession_and_future_excluded():
    submissions, facts = samples()
    rows = reconstruct_statements("AAPL", CIK, submissions, facts,
                                  date(2025, 12, 31), datetime.now(UTC))
    assert len(rows) == 2
    original, amended = rows
    assert original.source_reference == ORIGINAL
    assert original.normalized_values["revenue"] == 100
    assert amended.source_reference == AMENDED
    assert amended.normalized_values["revenue"] == 110
    assert amended.amendment_indicator == "AMENDMENT"
    assert original.provider_metadata["fact_provenance"]["revenue"]["accession"] == ORIGINAL
    assert original.provider_metadata["fact_provenance"]["revenue"]["tag"] == (
        "RevenueFromContractWithCustomerExcludingAssessedTax"
    )
    assert not original.revision_proven and not amended.revision_proven


def test_knowledge_boundary_rejects_premature_and_unverified_facts():
    submissions, facts = samples()
    original, amended = reconstruct_statements("AAPL", CIK, submissions, facts,
                                               date(2025, 12, 31), datetime.now(UTC))
    boundary = HistoricalKnowledgeBoundary()
    at = datetime(2024, 12, 1, tzinfo=UTC)
    assert boundary.classify(KnowledgeObservation(
        "fundamental", amended.source_reference, amended.accepted_at,
        amended.revision_proven), at) == KnowledgeState.NOT_YET_KNOWN
    assert boundary.classify(KnowledgeObservation(
        "fundamental", original.source_reference, original.accepted_at,
        original.revision_proven), at) == KnowledgeState.UNCERTAIN
    assert len(boundary.exclusions) == 2


def test_provider_http_contract_and_oos_lock():
    submissions, facts = samples()
    paths = []

    def handler(request):
        paths.append(request.url.path)
        assert "contact@example.org" in request.headers["User-Agent"]
        return httpx.Response(200, json=(submissions if "submissions" in request.url.path
                                         else facts))

    provider = SecEdgarHistoricalFundamentalProvider(
        "AgenticInvestingResearch contact@example.org", {"AAPL": CIK},
        transport=httpx.MockTransport(handler),
    )
    assert len(provider.statements("AAPL", through=date(2025, 12, 31))) == 2
    assert len(paths) == 2
    with pytest.raises(ValueError, match="out-of-sample"):
        provider.statements("AAPL", through=date(2026, 1, 1))
    assert len(paths) == 2


def test_conflicting_facts_fail_closed():
    submissions, facts = samples()
    facts["facts"]["us-gaap"]["NetIncomeLoss"]["units"]["USD"].append({
        "accn": ORIGINAL, "form": "10-K", "filed": "2024-11-01",
        "start": "2023-10-01", "end": "2024-09-30", "val": 99,
    })
    rows = reconstruct_statements("AAPL", CIK, submissions, facts,
                                  date(2025, 12, 31), datetime.now(UTC))
    assert "net_income" not in rows[0].normalized_values


def test_archived_submission_shard_preserves_old_accession():
    submissions, facts = samples()
    recent = submissions["filings"]["recent"]
    shard = {key: values[:1] for key, values in recent.items()}
    for key in recent:
        recent[key] = recent[key][1:]
    submissions["filings"]["files"] = [{
        "name": "CIK0000320193-submissions-001.json",
        "filingFrom": "2024-01-01", "filingTo": "2024-12-31",
    }]

    def handler(request):
        if "submissions-001" in request.url.path:
            return httpx.Response(200, json=shard)
        return httpx.Response(200, json=(submissions if "submissions" in request.url.path
                                         else facts))

    provider = SecEdgarHistoricalFundamentalProvider(
        "AgenticInvestingResearch contact@example.org", {"AAPL": CIK},
        transport=httpx.MockTransport(handler),
    )
    rows = provider.statements("AAPL", through=date(2025, 12, 31))
    assert {row.source_reference for row in rows} == {ORIGINAL, AMENDED}


def test_reconstruction_never_uses_future_amendment_or_unproven_values():
    submissions, facts = samples()
    original, amended = reconstruct_statements("AAPL", CIK, submissions, facts,
                                               date(2025, 12, 31), datetime.now(UTC))
    prior = original.model_copy(update={
        "period_end": date(2023, 9, 30),
        "accepted_at": datetime(2023, 11, 1, tzinfo=UTC),
        "normalized_values": {"revenue": 80, "net_income": 10},
        "source_reference": "prior-accession", "revision_proven": True,
    })
    original = original.model_copy(update={"revision_proven": True})
    amended = amended.model_copy(update={"revision_proven": True})
    before_amendment = reconstruct_quality_metrics(
        (prior, original, amended), datetime(2024, 12, 1, tzinfo=UTC),
        HistoricalKnowledgeBoundary(),
    )
    assert before_amendment["metrics"]["revenue_growth"] == 0.25
    assert before_amendment["source_accessions"] == ("prior-accession", ORIGINAL)
    after_amendment = reconstruct_quality_metrics(
        (prior, original, amended), datetime(2025, 2, 1, tzinfo=UTC),
        HistoricalKnowledgeBoundary(),
    )
    assert after_amendment["metrics"]["revenue_growth"] == 0.375
    assert after_amendment["source_accessions"] == ("prior-accession", AMENDED)
    unproven = reconstruct_quality_metrics(
        (original.model_copy(update={"revision_proven": False}),),
        datetime(2025, 2, 1, tzinfo=UTC), HistoricalKnowledgeBoundary(),
    )
    assert not unproven["metrics"] and not unproven["qualifying"]


def test_qualification_command_rejects_oos_before_provider_call():
    class NoCalls:
        def statements(self, *_args, **_kwargs):
            raise AssertionError("OOS provider accessed")

    with pytest.raises(ValueError, match="OOS"):
        summarize(NoCalls(), through=date(2026, 1, 2))
