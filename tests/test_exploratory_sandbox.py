"""The retrospective sandbox cannot confer qualification or access the holdout."""

import json
from datetime import datetime
from pathlib import Path

import pytest

from backtesting.models import ValidationGates
from experiment_lab.definitions import LONG_TERM_ID, SWING_ID, initial_definitions
from experiment_lab.exploratory_sandbox import (
    DEVELOPMENT,
    EXPECTED_DEFINITION_DIGESTS,
    SEALED_OOS,
    ExploratoryResearchRunner,
    ResearchEvidenceClass,
    _load_bounded,
)
from experiment_lab.historical_data import HistoricalResearchDataset
from experiment_lab.historical_research import ResearchRules
from risk.evaluator import digest


def _inputs(tmp_path: Path):
    dates = ("2023-01-03", "2023-01-04", "2025-01-02", "2025-01-03")
    symbols = ("AAPL", "MSFT", "NVDA", "AMZN", "GOOGL", "GOOG", "META",
               "TSLA", "PLTR", "INTC", "VOO")
    bars = []
    raw = []
    for day in dates:
        stamp = f"{day}T21:00:00+00:00"
        for symbol in symbols:
            bars.append({"symbol": symbol, "session_close": stamp,
                         "available_at": stamp, "adjustment_known_at": stamp,
                         "open": "100", "high": "101", "low": "99", "close": "100",
                         "volume": "1000"})
        raw.append({"symbol": "VOO", "timestamp": stamp, "open": "100",
                    "high": "101", "low": "99", "close": "100", "volume": "1000",
                    "feed": "iex", "adjustment_mode": "raw", "retrieved_at":
                    "2026-10-01T00:00:00+00:00", "provider": "test",
                    "source_digest": "fixture"})
    dataset = HistoricalResearchDataset.model_validate({
        "dataset_id": "fixture-exploratory", "version": "1", "provider": "fixture",
        "calendar_id": "fixture", "adjustment": "all",
        "acquired_at": "2026-10-01T00:00:00+00:00",
        "sessions": [f"{day}T21:00:00+00:00" for day in dates], "bars": bars,
        "is_synthetic": False, "session_calendar_complete": True})
    paths = tuple(tmp_path / name for name in ("dataset.json", "raw.json", "ledger.json"))
    for path, value in zip(paths, (dataset.model_dump(mode="json"),
                                   {"bars": raw, "holdout_exposed": False},
                                   {"events": [], "oos_exposed": False}), strict=True):
        path.write_text(json.dumps(value))
    return paths


def test_classification_and_frozen_inputs():
    assert {key: digest(value) for key, value in
            ((s.strategy_id, s) for s in initial_definitions())} == EXPECTED_DEFINITION_DIGESTS
    assert set(EXPECTED_DEFINITION_DIGESTS) == {LONG_TERM_ID, SWING_ID}
    assert ResearchEvidenceClass.EXPLORATORY_RETROSPECTIVE != ResearchEvidenceClass.QUALIFYING_HISTORICAL
    assert ResearchRules().swing_fast_sessions == 50
    assert ValidationGates(minimum_observations=126, minimum_trades=5,
                           max_drawdown="0.25", max_turnover=3,
                           acceptable_data_quality=(), zero_lookahead_violations=True,
                           zero_policy_bypasses=True).minimum_trades == 5


def test_bounded_inputs_refuse_oos_records(tmp_path):
    for kind, payload in (
        ("dataset", {"sessions": ["2026-01-02T21:00:00+00:00"], "bars": []}),
        ("dataset", {"sessions": [], "bars": [], "fundamentals": [{
            "period_end": "2026-01-02T00:00:00+00:00",
            "published_at": "2026-01-03T00:00:00+00:00"}]}),
        ("raw", {"bars": [{"timestamp": "2026-01-02T21:00:00+00:00"}]}),
        ("actions", {"events": [{"ex_date": "2026-01-02"}]}),
    ):
        path = tmp_path / "candidate.json"
        path.write_text(json.dumps(payload))
        with pytest.raises(ValueError, match="2026 OOS"):
            _load_bounded(path, kind=kind)


def test_runner_is_immutable_reproducible_and_nonexecuting(tmp_path, monkeypatch):
    paths = _inputs(tmp_path)
    runner = ExploratoryResearchRunner(*paths)
    with pytest.raises(ValueError, match="Only new"):
        runner.run("oos-request", tmp_path / "oos", periods=(DEVELOPMENT, SEALED_OOS))
    # Any accidental broker boundary crossing makes this test fail.
    from integrations.brokers.webull_sandbox import WebullSandboxAccess
    monkeypatch.setattr(WebullSandboxAccess, "submit_order",
                        lambda *args, **kwargs: pytest.fail("broker submission invoked"),
                        raising=False)
    output = tmp_path / "first"
    first = runner.run("fixed-v06-test", output)
    second = runner.run("fixed-v06-test", None)
    assert first["manifest"]["result_digest"] == second["manifest"]["result_digest"]
    assert json.loads((output / "manifest.json").read_text())["result_digest"] == first["manifest"]["result_digest"]
    assert [row["capital"] for row in first["result"]["results"]] == [
        "100000", "160", "100000", "160"]
    assert all(row["evidence_class"] == "EXPLORATORY_RETROSPECTIVE"
               and row["paper_eligibility"] == "NEVER_FROM_THIS_RESULT"
               and row["production_eligibility"] == "NEVER_FROM_THIS_RESULT"
               and row["forward_paper_sessions"] == 0
               and row["execution_available"] is False
               and row["oos_accessed"] is False
               and "CURRENT_VINTAGE" in row["benchmark_methodology"]
               for row in first["result"]["results"])
    assert first["result"]["qualifying_validation"] == "NOT_RUN"
    with pytest.raises(ValueError, match="Only new"):
        runner.run("fixed-v06-test", output)
    assert all(datetime.fromisoformat(item["session"]).year < 2026
               for row in first["result"]["results"] for item in row["curve"])
