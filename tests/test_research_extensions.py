import json
import runpy
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from agents.research import ResearchOrchestrator
from api.config import Settings
from api.main import create_app
from market_data.sample import SampleMarketDataProvider
from portfolio.exposure import PortfolioSnapshot
from portfolio.exposure import analyze as exposure
from reports.inputs import ResearchEvidence
from reports.markdown import render_markdown
from reports.models import ResearchReport
from technical.history import DailyClose, HistoryEvidence, PriceHistory, summarize

NOW = datetime(2026, 9, 28, 18, tzinfo=UTC)


def history(values):
    return HistoryEvidence(
        symbol="AAPL",
        source="test",
        adjustment="split",
        is_sample=True,
        bars=tuple(
            DailyClose(timestamp=NOW - timedelta(days=len(values) - index), close=value)
            for index, value in enumerate(values)
        ),
    )


@pytest.fixture
def frozen_clock(monkeypatch):
    class Clock:
        @staticmethod
        def now(tz):
            return NOW

    monkeypatch.setattr("agents.research.datetime", Clock)


@pytest.fixture
def snapshot():
    return {
        "source": "synthetic-test",
        "as_of": NOW.isoformat(),
        "currency": "USD",
        "is_sample": True,
        "holdings": [
            {
                "account_id": "one",
                "symbol": "AAPL",
                "quantity": "10",
                "price": "100",
                "price_as_of": NOW.isoformat(),
                "price_source": "test",
                "currency": "USD",
                "sector": "Technology",
            },
            {
                "account_id": "two",
                "symbol": "AAPL",
                "quantity": "-4",
                "price": "100",
                "price_as_of": NOW.isoformat(),
                "price_source": "test",
                "currency": "USD",
                "sector": "Technology",
            },
            {
                "account_id": "one",
                "symbol": "MSFT",
                "quantity": "5",
                "price": "100",
                "price_as_of": NOW.isoformat(),
                "price_source": "test",
                "currency": "USD",
                "sector": "Technology",
            },
        ],
        "cash": [{"account_id": "one", "currency": "USD", "amount": "900"}],
    }


def test_flat_indicators():
    result = summarize(history([100] * 60))
    assert result.rsi14 == 50
    assert result.macd == result.macd_signal == result.macd_histogram == 0
    assert result.bollinger_lower == result.bollinger_upper == 100
    assert result.return_20 == result.volatility_20_annualized == 0
    assert result.max_drawdown == result.drawdown_from_peak == 0
    assert result.missing_indicators == []


def test_trending_macd_and_rsi():
    result = summarize(history(list(range(1, 61))))
    assert result.rsi14 == 100
    assert result.macd == result.macd_signal == 7
    assert result.macd_histogram == 0
    assert result.return_20 == Decimal("0.5")
    assert summarize(history(list(range(60, 0, -1)))).rsi14 == 0


def test_wilder_rsi_known_seed_and_smoothing():
    values = list(
        map(
            Decimal,
            [
                "44.34",
                "44.09",
                "44.15",
                "43.61",
                "44.33",
                "44.83",
                "45.10",
                "45.42",
                "45.84",
                "46.08",
                "45.89",
                "46.03",
                "45.61",
                "46.28",
                "46.28",
            ],
        )
    )
    assert float(summarize(history(values)).rsi14) == pytest.approx(70.464135, abs=0.000001)
    assert float(summarize(history([*values, Decimal(46)])).rsi14) == pytest.approx(
        66.249619, abs=0.000001
    )


def test_bollinger_population_variance_and_drawdown():
    result = summarize(history(list(range(1, 21))))
    assert result.bollinger_upper == Decimal("10.5") + 2 * Decimal("33.25").sqrt()
    assert result.bollinger_lower == Decimal("10.5") - 2 * Decimal("33.25").sqrt()
    result = summarize(history([100, 120, 90, 110, 80, 130, 100]))
    assert result.max_drawdown == Decimal(80) / 120 - 1
    assert result.drawdown_from_peak == Decimal(100) / 130 - 1


def test_volatility_uses_twenty_sample_returns():
    # Ten +10% and ten -10% returns: sample variance = .2/19.
    values = [Decimal(100)]
    for index in range(20):
        values.append(values[-1] * (Decimal("1.1") if index % 2 == 0 else Decimal("0.9")))
    expected = (Decimal("0.2") / 19 * 252).sqrt()
    assert float(summarize(history(values)).volatility_20_annualized) == pytest.approx(
        float(expected)
    )


@pytest.mark.parametrize(
    "count,field",
    [
        (14, "rsi14"),
        (19, "bollinger_upper"),
        (20, "return_20"),
        (25, "macd"),
        (33, "macd_signal"),
        (49, "sma50"),
    ],
)
def test_indicator_warmup(count, field):
    assert getattr(summarize(history([100] * count)), field) is None
    assert getattr(summarize(history([100] * (count + 1))), field) is not None


def test_same_session_duplicates_and_missing_provenance_rejected():
    bar = DailyClose(timestamp=NOW, close=100)
    with pytest.raises(ValidationError, match="one close"):
        PriceHistory(
            symbol="AAPL", bars=(bar, DailyClose(timestamp=NOW + timedelta(hours=1), close=101))
        )
    with pytest.raises(ValidationError):
        HistoryEvidence(symbol="AAPL", bars=())


def test_future_session_exclusion_and_json_priority(frozen_clock):
    class NoHistoryCalls(SampleMarketDataProvider):
        def get_history(self, symbol):
            pytest.fail("JSON history takes priority")

    supplied = history([100] * 50)
    supplied = supplied.model_copy(
        update={"bars": (*supplied.bars, DailyClose(timestamp=NOW, close=999))}
    )
    report = ResearchOrchestrator(NoHistoryCalls()).research(
        "AAPL", ResearchEvidence(price_history=supplied)
    )
    assert report.technicals.bars_used == 50
    assert report.technicals.sma20 == 100
    assert len(report.price_history.bars) == 51  # Preserve original evidence.
    assert any("excluded" in warning for warning in report.risks)


def test_portfolio_aggregation_preserves_offsetting_gross(snapshot):
    result = exposure(PortfolioSnapshot.model_validate(snapshot), "AAPL", NOW)
    assert result.long_value == 1500 and result.short_value == 400
    assert result.equity == 2000 and result.gross_exposure == 1900
    assert result.gross_leverage == Decimal("0.95")
    assert result.net_leverage == Decimal("0.55")
    assert result.cash_weight == Decimal("0.45")
    assert result.by_symbol["AAPL"].net_value == 600
    assert result.by_symbol["AAPL"].gross_value == 1400
    assert result.researched_symbol_exposure.gross_weight == Decimal("0.7")
    assert result.by_sector["Technology"].gross_weight == Decimal("0.95")
    assert sum(item.net_value for item in result.by_account.values()) == 1100


def test_cash_only_empty_and_absent_symbol(snapshot):
    snapshot["holdings"] = []
    result = exposure(PortfolioSnapshot.model_validate(snapshot), "MSFT", NOW)
    assert result.equity == 900 and result.cash_weight == 1
    assert result.researched_symbol_exposure.gross_weight == 0
    snapshot["cash"] = []
    result = exposure(PortfolioSnapshot.model_validate(snapshot), "MSFT", NOW)
    assert result.equity == 0 and result.cash_weight is None
    assert result.researched_symbol_exposure.gross_weight is None


def test_nonpositive_equity_future_and_stale(snapshot):
    snapshot["cash"][0]["amount"] = "-2000"
    result = exposure(PortfolioSnapshot.model_validate(snapshot), "AAPL", NOW)
    assert result.equity == -900 and result.gross_leverage is None
    assert result.by_symbol["AAPL"].net_weight is None
    future = exposure(
        PortfolioSnapshot.model_validate(snapshot), "AAPL", NOW - timedelta(seconds=1)
    )
    assert future.state == "unavailable" and future.equity is None
    stale = exposure(PortfolioSnapshot.model_validate(snapshot), "AAPL", NOW + timedelta(days=2))
    assert sum("24 hours" in warning for warning in stale.warnings) == 2


@pytest.mark.parametrize(
    "fault", ["currency", "duplicate", "sector", "future_price", "infinite", "derivative"]
)
def test_bad_snapshots_rejected(snapshot, fault):
    if fault == "currency":
        snapshot["cash"][0]["currency"] = "EUR"
    elif fault == "duplicate":
        snapshot["holdings"].append(snapshot["holdings"][0])
    elif fault == "sector":
        snapshot["holdings"][1]["sector"] = "Energy"
    elif fault == "future_price":
        snapshot["holdings"][0]["price_as_of"] = (NOW + timedelta(seconds=1)).isoformat()
    elif fault == "infinite":
        snapshot["holdings"][0]["quantity"] = "Infinity"
    else:
        snapshot["holdings"][0]["asset_type"] = "option"
    with pytest.raises(ValidationError):
        PortfolioSnapshot.model_validate(snapshot)


def test_risk_rules_and_references(snapshot, frozen_clock):
    snapshot["cash"][0]["amount"] = "0"
    evidence = ResearchEvidence(portfolio=snapshot, price_history=history(list(range(60, 0, -1))))
    report = ResearchOrchestrator(SampleMarketDataProvider()).research("AAPL", evidence)
    codes = {finding.code for finding in report.risk_findings}
    assert {
        "gross_leverage",
        "short_exposure",
        "symbol_concentration",
        "sector_concentration",
        "historical_drawdown",
        "rsi_extreme",
    } <= codes
    assert report.bear_case and report.assessment.observations
    payload = report.model_dump(mode="json")
    for item in [*report.risk_findings, *report.assessment.observations]:
        for ref in item.evidence_refs:
            resolved = payload
            for part in ref.split("/")[1:]:
                key = part.replace("~1", "/").replace("~0", "~")
                resolved = resolved[int(key)] if isinstance(resolved, list) else resolved[key]
            assert resolved is not None


def test_no_concentration_at_exact_threshold(snapshot, frozen_clock):
    snapshot["holdings"] = [snapshot["holdings"][0]]
    snapshot["cash"][0]["amount"] = "3000"  # 1000 / 4000 = 25%.
    report = ResearchOrchestrator(SampleMarketDataProvider()).research(
        "AAPL", ResearchEvidence(portfolio=snapshot)
    )
    assert "symbol_concentration" not in {item.code for item in report.risk_findings}


def test_markdown_api_persistence_and_validation(snapshot, frozen_clock, tmp_path):
    settings = Settings(_env_file=None, database_url=f"sqlite:///{tmp_path / 'reports.db'}")
    payload = {"portfolio": snapshot, "price_history": history([100] * 60).model_dump(mode="json")}
    with TestClient(create_app(settings, SampleMarketDataProvider())) as client:
        response = client.post("/research/AAPL", json=payload)
        assert response.status_code == 201, response.text
        report = response.json()
        assert report["portfolio"]["equity"] == "2000"
        assert "portfolio_exposure" not in report["missing_data"]
        assert report["assessment"]["method"] == "deterministic-v1"
        payload["price_history"]["symbol"] = "MSFT"
        assert client.post("/research/AAPL", json=payload).status_code == 422
    with TestClient(create_app(settings, SampleMarketDataProvider())) as client:
        url = f"/reports/{report['id']}"
        assert client.get(url).json() == report
        markdown = client.get(url + "?format=markdown")
        assert markdown.status_code == 200
        assert markdown.headers["content-type"].startswith("text/markdown")
        assert "attachment" in markdown.headers["content-disposition"]
        assert "## Portfolio exposure" in markdown.text
        assert "## Risk findings" in markdown.text
        assert client.get(url + "?format=html").status_code == 422


def test_markdown_external_content_is_escaped(frozen_clock):
    report = ResearchOrchestrator(SampleMarketDataProvider()).research("AAPL")
    report.catalysts = ["<script>alert(1)</script>\n# forged\n![image](https://example.com/track)"]
    result = render_markdown(report)
    assert "<script>" not in result
    assert "\n# forged" not in result
    assert "![image](" not in result
    assert "&lt;script&gt;" in result


def test_version_three_report_reads_without_new_fields(frozen_clock):
    payload = ResearchOrchestrator(SampleMarketDataProvider()).research("AAPL").model_dump()
    for field in ("analysis_version", "portfolio", "assessment", "risk_findings", "risk_policy"):
        payload.pop(field)
    payload["schema_version"] = "3"
    report = ResearchReport.model_validate(payload)
    assert report.portfolio is None and report.assessment is None
    assert "investment research" in render_markdown(report)


def test_fundamental_and_event_risks(frozen_clock):
    path = Path(__file__).resolve().parents[1] / "docs/examples/research-evidence.json"
    payload = json.loads(path.read_text(encoding="utf-8"))
    payload["fundamentals"]["current"].update(
        revenue="90000000", net_income="-1", equity="-1", operating_cash_flow="-1"
    )
    payload["news"]["catalysts"][0]["event_at"] = (NOW + timedelta(days=1)).isoformat()
    report = ResearchOrchestrator(SampleMarketDataProvider()).research(
        "AAPL", ResearchEvidence.model_validate(payload)
    )
    assert {
        "revenue_contraction",
        "net_loss",
        "negative_fcf",
        "nonpositive_book_equity",
        "near_term_catalyst",
    } <= {item.code for item in report.risk_findings}
    assert len(report.bear_case) == 3


def test_complete_documented_example(frozen_clock):
    path = Path(__file__).resolve().parents[1] / "docs/examples/build_full_evidence.py"
    payload = runpy.run_path(str(path))["build"]()
    report = ResearchOrchestrator(SampleMarketDataProvider()).research(
        "AAPL",
        ResearchEvidence.model_validate(payload),
    )
    assert report.portfolio.equity == 5000
    assert report.portfolio.cash_weight == Decimal("0.582")
    assert report.portfolio.researched_symbol_exposure.gross_weight == Decimal("0.318")
    assert report.technicals.macd == 7
    assert report.technicals.missing_indicators == []
    assert report.missing_data == ["investment_thesis"]
    assert report.assessment and report.bull_case
    assert "## Fundamentals" in render_markdown(report)
