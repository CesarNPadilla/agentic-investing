"""Fail-closed research data qualification without live credentials or orders."""

from datetime import UTC, date, datetime, timedelta
from pathlib import Path

import httpx
import pytest

from experiment_lab.alpaca_historical import AlpacaRawPriceProvider
from experiment_lab.corporate_actions import action_known, normalize_alpaca_action
from experiment_lab.fmp_historical import (
    FmpHistoricalFundamentalProvider,
    load_fmp_credential,
    normalize_statement,
)
from experiment_lab.historical_records import RawHistoricalPriceBar
from experiment_lab.knowledge_boundary import (
    HistoricalKnowledgeBoundary,
    KnowledgeObservation,
    KnowledgeState,
)
from experiment_lab.qualification_audit import audit
from experiment_lab.swing_diagnostic import diagnose

AT = datetime(2025, 1, 2, 21, tzinfo=UTC)


def test_fiscal_end_and_filing_date_do_not_imply_availability():
    row = {"symbol": "AAPL", "date": "2024-09-30", "period": "FY",
           "filingDate": "2024-11-01", "acceptedDate": "2024-11-01 10:00:00",
           "reportedCurrency": "USD", "revenue": 100}
    statement = normalize_statement(row, "income", AT)
    assert statement.period_end == date(2024, 9, 30)
    assert statement.accepted_at is None  # provider omitted timezone
    boundary = HistoricalKnowledgeBoundary()
    assert not boundary.require(KnowledgeObservation(
        "fundamental", statement.raw_payload_digest, statement.accepted_at,
        statement.revision_proven,
    ), AT)
    assert boundary.exclusions[-1]["state"] == "UNCERTAIN"


def test_accepted_time_and_revision_both_required():
    boundary = HistoricalKnowledgeBoundary()
    assert boundary.classify(KnowledgeObservation("fundamental", "x", AT + timedelta(seconds=1),
                                                   True), AT) == KnowledgeState.NOT_YET_KNOWN
    assert boundary.classify(KnowledgeObservation("fundamental", "x", AT, False),
                             AT) == KnowledgeState.UNCERTAIN
    assert boundary.classify(KnowledgeObservation("fundamental", "x", AT, True),
                             AT) == KnowledgeState.KNOWN
    assert boundary.classify(KnowledgeObservation("valuation_input", "x", None, True, False),
                             AT) == KnowledgeState.UNAVAILABLE
    assert len(boundary.exclusions) == 3


def test_external_credential_loader_and_sanitized_provider_error(tmp_path: Path):
    secret = "FAKE_DO_NOT_PERSIST_9835"
    env = tmp_path / "FMP.env"
    env.write_text("FMP_API_KEY=" + secret, encoding="utf-8")
    assert load_fmp_credential(env) == secret

    def handler(request):
        assert request.url.params["apikey"] == secret
        return httpx.Response(402, text=secret)

    provider = FmpHistoricalFundamentalProvider(secret, transport=httpx.MockTransport(handler))
    with pytest.raises(ValueError) as error:
        provider.statements("AAPL", through=date(2025, 12, 31))
    assert secret not in str(error.value)


def test_raw_bar_immutable_and_corporate_action_separate():
    raw = RawHistoricalPriceBar(symbol="AAPL", timestamp=AT, open="100", high="101",
                                low="99", close="100", volume=1000, feed="iex",
                                adjustment_mode="raw", retrieved_at=AT + timedelta(days=1),
                                provider="Alpaca", source_digest="a" * 64)
    with pytest.raises((TypeError, ValueError)):
        raw.close = 200
    action = normalize_alpaca_action({"type": "forward_split", "symbol": "AAPL",
                                      "ex_date": "2025-01-02"}, AT)
    assert action.announced_at is None
    boundary = HistoricalKnowledgeBoundary()
    assert not action_known(action, AT, boundary)
    assert boundary.exclusions[0]["state"] == "UNCERTAIN"


def test_raw_adapter_requests_raw_and_honors_cutoff():
    def handler(request):
        assert request.url.params["adjustment"] == "raw"
        assert request.url.params["end"] == "2025-01-03"
        return httpx.Response(200, json={"symbol": "AAPL", "bars": [{
            "t": "2025-01-02T05:00:00Z", "o": 100, "h": 101, "l": 99,
            "c": 100, "v": 1000,
        }], "next_page_token": None})

    provider = AlpacaRawPriceProvider("fake", "fake", transport=httpx.MockTransport(handler),
                                     feed="iex")
    bars = provider.bars(("AAPL",), date(2025, 1, 2), date(2025, 1, 3))
    assert len(bars) == 1 and bars[0].adjustment_mode == "raw"


def test_swing_diagnostic_rejects_oos_and_does_not_change_rules():
    with pytest.raises(ValueError):
        diagnose({"role": "out_of_sample", "strategy_id": "SWING_TREND_MOMENTUM",
                  "capital": "100000"})


def test_audit_rejects_oos_bar_before_writing(tmp_path: Path):
    import json

    raw, plan, results = tmp_path / "raw.json", tmp_path / "plan.json", tmp_path / "results"
    results.mkdir()
    plan.write_text(json.dumps({"plan_id": "test", "gates": {}}), encoding="utf-8")
    raw.write_text(json.dumps({"scope": "DEVELOPMENT_AND_VALIDATION_ONLY",
                               "adjustment_mode": "raw", "holdout_exposed": False,
                               "bars": [{"timestamp": "2026-01-02T21:00:00Z"}]}),
                   encoding="utf-8")
    output = tmp_path / "audit.json"
    with pytest.raises(ValueError, match="OOS"):
        audit(raw, plan, results, output)
    assert not output.exists()
