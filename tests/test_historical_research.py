"""Generated bars here verify software behavior; they are not empirical evidence."""

from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest

from backtesting.models import Period, ValidationGates
from experiment_lab.historical_data import (
    FundamentalPoint,
    HistoricalResearchDataset,
    MarketBar,
)
from experiment_lab.historical_research import (
    HistoricalResearchPlan,
    HistoricalResearchStudy,
    ResearchRules,
    robustness_summary,
    simulate,
)
from experiment_lab.historical_run import run
from risk.evaluator import digest


def fixture_dataset():
    sessions = tuple(datetime(2020, 1, 1, 21, tzinfo=UTC) + timedelta(days=i)
                     for i in range(240))
    bars = []
    for i, session in enumerate(sessions):
        for symbol in ("AAPL", "VOO"):
            price = Decimal(100 + i // 5) + Decimal(i % 5) / 10
            if symbol == "VOO":
                price = Decimal(100) + Decimal(i) / 10
            bars.append(MarketBar(
                symbol=symbol, session_close=session, available_at=session,
                adjustment_known_at=session, open=price, high=price + 1,
                low=price - 1, close=price, volume=Decimal(1500 if i % 3 == 0 else 1000),
            ))
    metrics = {
        "revenue_growth": Decimal("0.12"), "free_cash_flow": Decimal(1000000),
        "net_debt_to_ebitda": Decimal(2), "free_cash_flow_yield": Decimal("0.04"),
    }
    fundamentals = tuple(FundamentalPoint(
        symbol="AAPL", metric=name, value=value,
        period_end=sessions[180], published_at=sessions[190],
        available_at=sessions[190], source_id="test-source", revision_proven=True,
    ) for name, value in metrics.items())
    # This deliberately constructed test object is never exported as a study artifact.
    return HistoricalResearchDataset(
        dataset_id="unit-test-only", version="1", provider="test-double",
        calendar_id="test-calendar", adjustment="all", acquired_at=sessions[-1],
        sessions=sessions, bars=tuple(bars), fundamentals=fundamentals,
        corporate_actions_complete=True, session_calendar_complete=True,
        point_in_time_adjustments=True, point_in_time_fundamentals=True,
        is_synthetic=False,
    )


def fixture_plan(dataset, *, trades=1):
    periods = tuple(Period(role=role, start=dataset.sessions[a].date(),
                           end=dataset.sessions[b].date())
                    for role, a, b in (("development", 210, 219),
                                       ("validation", 220, 229),
                                       ("out_of_sample", 230, 239)))
    return HistoricalResearchPlan(
        plan_id="unit-test-plan", created_at=dataset.sessions[-1],
        dataset_digest=digest(dataset), symbols=("AAPL",), periods=periods,
        source_version="unit-test-code",
        rules=ResearchRules(long_review_sessions=1, swing_rsi_lower=0,
                            swing_rsi_upper=100),
        gates=ValidationGates(minimum_observations=10, minimum_trades=trades,
                              max_drawdown=Decimal("0.5"), max_turnover=Decimal(10),
                              acceptable_data_quality=()),
    )


def test_candidate_ledger_is_research_only_and_capital_modes_separate():
    data = fixture_dataset()
    plan = fixture_plan(data)
    research = simulate(data, plan, plan.periods[0], "LONG_TERM_QUALITY_GROWTH",
                        plan.research_capital)
    small = simulate(data, plan, plan.periods[0], "LONG_TERM_QUALITY_GROWTH", Decimal(160))
    assert research["status"] == "COMPLETED"
    assert research["metrics"]["number_of_trades"] > 0
    assert all(t["policy_status"] == "NOT_SUBMITTED_RESEARCH_ONLY" for t in research["trades"])
    assert small["metrics"]["number_of_trades"] > 0
    assert all(Decimal(t["quantity"]) == Decimal(1) for t in small["trades"])
    assert max(Decimal(c["deployed_entry_notional"]) for c in small["curve"]) <= 160
    assert research["execution_available"] is False


def test_unproven_fundamental_revision_cannot_enter_long_term_signal():
    data = fixture_dataset()
    altered = data.model_copy(update={
        "fundamentals": tuple(point.model_copy(update={"revision_proven": False})
                              for point in data.fundamentals),
    })
    plan = fixture_plan(altered)
    row = simulate(altered, plan, plan.periods[0], "LONG_TERM_QUALITY_GROWTH",
                   plan.research_capital)
    assert row["metrics"]["number_of_trades"] == 0
    assert row["knowledge_exclusions"]
    assert all(item["state"] == "UNCERTAIN" for item in row["knowledge_exclusions"])


def test_frozen_gates_prevent_premature_holdout():
    data = fixture_dataset()
    study = HistoricalResearchStudy(fixture_plan(data, trades=100), data)
    with pytest.raises(ValueError, match="Untouched OOS"):
        study.out_of_sample()
    study.development()
    _, checks = study.validation()
    assert checks["minimum_trades"] == "FAIL"
    assert study.phase == "VALIDATION_FAILED"
    assert "out_of_sample" not in study.results
    with pytest.raises(ValueError, match="Untouched OOS"):
        study.out_of_sample()


def test_holdout_stays_locked_even_after_validation_phase_passes():
    data = fixture_dataset()
    study = HistoricalResearchStudy(fixture_plan(data), data)
    study.phase = "VALIDATION_PASSED"
    with pytest.raises(ValueError, match="separately authorized release"):
        study.out_of_sample()
    assert "out_of_sample" not in study.results


def test_missing_provenance_is_nonqualifying_even_if_metrics_compute():
    data = fixture_dataset().model_copy(update={"point_in_time_adjustments": False})
    plan = fixture_plan(data)
    row = simulate(data, plan, plan.periods[0], "SWING_TREND_MOMENTUM",
                   plan.research_capital)
    assert row["status"] == "COMPLETED"
    assert "ADJUSTMENT_VINTAGE_UNVERIFIED" in row["data_quality"]
    assert row["lookahead_violations"] == 1
    assert row["evidence_class"] == "RETROSPECTIVE_NONQUALIFYING"


def test_unset_validation_gates_rejected():
    data = fixture_dataset()
    plan = fixture_plan(data)
    with pytest.raises(ValueError, match="validation gates"):
        HistoricalResearchPlan.model_validate(plan.model_dump() | {
            "gates": ValidationGates(minimum_observations=10).model_dump(),
        })


def test_staged_artifacts_never_write_failed_holdout(tmp_path):
    data = fixture_dataset()
    plan = fixture_plan(data, trades=100)
    plan_path, data_path = tmp_path / "plan.json", tmp_path / "data.json"
    plan_path.write_text(plan.model_dump_json(), encoding="utf-8")
    data_path.write_text(data.model_dump_json(), encoding="utf-8")
    output, registry = tmp_path / "output", tmp_path / "registry.sqlite"
    status = run(plan_path, data_path, output, registry)
    assert status["phase"] == "VALIDATION_FAILED"
    assert not (output / "out-of-sample.json").exists()
    assert (output / "development-sensitivity.json").exists()
    with pytest.raises(ValueError, match="exposed|empty"):
        run(plan_path, data_path, tmp_path / "another-output", registry)


def test_robustness_summary_is_descriptive_and_excludes_holdout():
    data = fixture_dataset()
    plan = fixture_plan(data)
    development = (simulate(data, plan, plan.periods[0], "LONG_TERM_QUALITY_GROWTH",
                            plan.research_capital),)
    validation = (simulate(data, plan, plan.periods[1], "LONG_TERM_QUALITY_GROWTH",
                           plan.research_capital),)
    report = robustness_summary(development, validation)
    assert report[0]["status"] == "DESCRIPTIVE_ONLY"
    assert report[0]["holdout_evaluated"] is False
    assert report[0]["robustness_established"] is False
