"""Opt-in v0.8 behavior; original simulator and policy remain unchanged."""

from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from inspect import getsource

import pytest

from backtesting.models import Period, ValidationGates
from experiment_lab import historical_research
from experiment_lab.controlled_experiments_v08 import SCENARIOS, _exposure_decomposition
from experiment_lab.definitions import initial_definitions
from experiment_lab.historical_data import HistoricalResearchDataset
from experiment_lab.historical_research import HistoricalResearchPlan, ResearchRules, simulate
from risk.evaluator import digest
from risk.policy import InvestmentPolicy


def _fixture():
    days = []
    day = date(2023, 1, 2)
    while len(days) < 212:
        if day.weekday() < 5:
            days.append(day)
        day += timedelta(days=1)
    sessions = [datetime.combine(day, datetime.min.time(), UTC).replace(hour=21)
                for day in days]
    bars = [{"symbol": symbol, "session_close": instant,
             "available_at": instant, "adjustment_known_at": instant,
             "open": "100", "high": "101", "low": "99", "close": "100",
             "volume": "1000"}
            for instant in sessions for symbol in ("AAPL", "VOO")]
    dataset = HistoricalResearchDataset.model_validate({
        "dataset_id": "controlled-fixture", "version": "1", "provider": "fixture",
        "calendar_id": "fixture", "adjustment": "all",
        "acquired_at": "2026-10-01T00:00:00+00:00", "sessions": sessions,
        "bars": bars, "session_calendar_complete": True, "is_synthetic": False})
    development = Period(role="development", start=days[0], end=days[-1])
    plan = HistoricalResearchPlan(
        plan_id="fixture", created_at=datetime(2026, 10, 1, tzinfo=UTC),
        dataset_digest=dataset.content_digest, symbols=("AAPL",),
        periods=(development,
                 Period(role="validation", start=date(2025, 1, 2), end=date(2025, 12, 31)),
                 Period(role="out_of_sample", start=date(2026, 1, 2),
                        end=date(2026, 9, 29))),
        gates=ValidationGates(minimum_observations=126, minimum_trades=5,
                              max_drawdown="0.25", max_turnover=3,
                              acceptable_data_quality=(), zero_lookahead_violations=True,
                              zero_policy_bypasses=True), source_version="fixture")
    return dataset, plan, development


@pytest.mark.parametrize("exit_reason", ("TREND_FAILURE", "ATR_STOP", "HOLDING_LIMIT"))
def test_h01_requires_distinct_post_exit_false_then_true(monkeypatch, exit_reason):
    dataset, plan, period = _fixture()

    def predicate(strategy, history, dataset, symbol, cutoff, rules, held,
                  held_sessions, stop, boundary):
        n = len(history)
        if held and n == 203:
            return "sell", exit_reason, None
        if not held and n in (201, 204, 206):
            return "buy", "TREND_MOMENTUM", Decimal(98)
        return None, "NO_SIGNAL", None

    monkeypatch.setattr(historical_research, "_signal", predicate)
    result = simulate(dataset, plan, period, "SWING_TREND_MOMENTUM", Decimal(100000),
                      reentry_reset=True)
    events = [a["event"] for a in result["reentry_state_audit"]]
    assert "EXIT_FILLED_DISARMED" in events
    assert "EXIT_SESSION_CANNOT_ARM" in events
    assert "POST_EXIT_FALSE_ARMED" in events
    assert "LATER_TRUE_PENDING_ENTRY" in events
    exits = [t for t in result["trades"] if t["side"] == "sell"]
    buys = [t for t in result["trades"] if t["side"] == "buy"]
    assert exits[0]["reason"] == exit_reason
    assert len(buys) == 2
    assert buys[1]["signal"] > exits[0]["filled_at"]


def test_h01_missing_observation_does_not_arm(monkeypatch):
    dataset, plan, period = _fixture()

    def predicate(strategy, history, dataset, symbol, cutoff, rules, held,
                  held_sessions, stop, boundary):
        n = len(history)
        if held and n == 203:
            return "sell", "ATR_STOP", None
        if not held and n in (201, 204, 206):
            return "buy", "TREND_MOMENTUM", Decimal(98)
        if n == 205:
            return None, "INSUFFICIENT_WARMUP", None
        return None, "NO_SIGNAL", None

    monkeypatch.setattr(historical_research, "_signal", predicate)
    result = simulate(dataset, plan, period, "SWING_TREND_MOMENTUM", Decimal(100000),
                      reentry_reset=True)
    assert "MISSING_DATA_REMAIN_DISARMED" in [a["event"] for a in
                                             result["reentry_state_audit"]]
    assert sum(t["side"] == "buy" for t in result["trades"]) == 1


def test_h03_instrumentation_keeps_baseline_fills_and_overlaps():
    dataset, plan, period = _fixture()
    plain = simulate(dataset, plan, period, "SWING_TREND_MOMENTUM", Decimal(100000))
    measured = simulate(dataset, plan, period, "SWING_TREND_MOMENTUM", Decimal(100000),
                        exposure_diagnostics=True)
    assert plain["trades"] == measured["trades"]
    assert plain["metrics"] == measured["metrics"]
    assert len(measured["exposure_audit"]) == len(dataset.sessions) - 1
    assert _exposure_decomposition(measured)["constraints_may_overlap"] is True
    assert measured["risk_engine_outcomes"] == "NOT_EXERCISED"
    overlapping = _exposure_decomposition({
        "exposure_audit": [{"session": "2025-01-02", "original_entry_eligible": False,
                            "constraints": ["SIGNAL_SCARCITY", "EXISTING_POSITION"]}],
        "curve": [{"session": "2025-01-02"}, {"session": "2025-01-03"}],
        "trades": (), "skipped_orders": ()})
    assert overlapping["constraint_counts_overlapping"] == {
        "SIGNAL_SCARCITY": 1, "EXISTING_POSITION": 1}
    assert overlapping["constraints_may_overlap"] is True


def test_h04_fixed_costs_and_isolated_1000_capital(monkeypatch):
    from integrations.brokers.execution import SyntheticExecutionBroker
    from integrations.brokers.orders import OrderExecutionAdapter
    from integrations.brokers.webull_sandbox import WebullSandboxAccess

    def forbidden(*args, **kwargs):
        pytest.fail("Exploratory simulation reached a broker")

    monkeypatch.setattr(SyntheticExecutionBroker, "fill", forbidden)
    monkeypatch.setattr(OrderExecutionAdapter, "submit_limit_order", forbidden)
    monkeypatch.setattr(WebullSandboxAccess, "place_order", forbidden)
    monkeypatch.setattr(WebullSandboxAccess, "submit_order", forbidden, raising=False)
    assert SCENARIOS == (("NO_COST_MATCHED_COUNTERFACTUAL", Decimal(0),
                          Decimal(0), Decimal(0)),
                         ("BASELINE", Decimal("0.10"), Decimal(2), Decimal(5)),
                         ("STRESSED", Decimal("0.25"), Decimal(4), Decimal(10)))
    dataset, plan, period = _fixture()
    monkeypatch.setattr(historical_research, "_signal",
                        lambda strategy, history, dataset, symbol, cutoff, rules, held,
                        held_sessions, stop, boundary: (
                            ("buy", "TREND_MOMENTUM", Decimal(98))
                            if not held and len(history) == 201 else
                            ("sell", "ATR_STOP", None) if held and len(history) == 203 else
                            (None, "NO_SIGNAL", None)))
    no_cost_rules = ResearchRules().model_copy(update={"commission": Decimal(0),
                                               "spread_bps": Decimal(0),
                                               "slippage_bps": Decimal(0)})
    no_cost = simulate(dataset, plan.model_copy(update={"rules": no_cost_rules}), period,
                       "SWING_TREND_MOMENTUM", Decimal(100000))
    baseline = simulate(dataset, plan, period, "SWING_TREND_MOMENTUM", Decimal(100000))
    assert no_cost["metrics"]["estimated_execution_friction"] == "0"
    assert Decimal(baseline["metrics"]["estimated_execution_friction"]) > 0
    assert Decimal(no_cost["metrics"]["total_return"]) > Decimal(
        baseline["metrics"]["total_return"])
    small = simulate(dataset, plan, period, "SWING_TREND_MOMENTUM", Decimal(1000),
                     feasibility_capital=Decimal(1000), exposure_diagnostics=True)
    assert all(Decimal(t["quantity"]) == int(Decimal(t["quantity"])) for t in small["trades"])
    assert InvestmentPolicy().agent_experimental_capital_limit == 160
    assert {s.strategy_version for s in initial_definitions()} == {"1.0.0"}
    assert digest(plan.gates) == digest(plan.model_copy().gates)


def test_h02_has_no_implementation_or_option():
    assert "holding_exit" not in simulate.__code__.co_varnames
    assert 'return "sell", "HOLDING_LIMIT", None' in getsource(historical_research._signal)
