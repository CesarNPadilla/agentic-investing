import json
from uuid import uuid4

import pytest

from risk.paper_state import PaperState, PaperStateError
from scripts.check_alpaca_status_stream import probe
from strategies.paper_etf_scope import selected_symbol
from tests.test_status_stream_probe import Stream
from workers.paper_event_observer import PaperEventObserver


def test_etf_scope_cannot_enable_execution_or_add_intc(tmp_path):
    folder = tmp_path / "conf"
    folder.mkdir()
    spec = {
        "strategy_id": "PAPER_ETF_CONTROL_PLUMBING",
        "version": "1.0.0",
        "allowed_symbols": ["SCHB"],
        "disabled_symbols": ["INTC"],
        "instrument_category": "ETF_ONLY",
        "execution_available": False,
        "trial_started": False,
        "live_authorized": False,
    }
    path = folder / "paper-etf-plumbing.json"
    path.write_text(json.dumps(spec), encoding="utf-8")
    assert selected_symbol(tmp_path) == "SCHB"
    for field, value in (
        ("execution_available", True),
        ("allowed_symbols", ["SCHB", "INTC"]),
        ("live_authorized", True),
        ("version", "unknown"),
    ):
        path.write_text(json.dumps(dict(spec, **{field: value})), encoding="utf-8")
        with pytest.raises(ValueError):
            selected_symbol(tmp_path)


def test_etf_events_check_risk_and_intc_latches_without_dispatch(tmp_path):
    state = PaperState.initialize(tmp_path / "paper.sqlite", account_binding="a" * 64)
    calls = []

    def cycle():
        calls.append(True)
        return {
            "account_observed": True,
            "blockers": ["STATUS_BOOTSTRAP_UNQUALIFIED"],
            "execution_available": False,
        }

    observer = PaperEventObserver(state, cycle, account_binding="a" * 64, symbol="SCHB")
    observer.on_event({"event": "fill", "order": {"id": str(uuid4()), "symbol": "SCHB"}})
    with pytest.raises(PaperStateError):
        observer.on_event({"event": "fill", "order": {"id": str(uuid4()), "symbol": "INTC"}})
    assert len(calls) == 1
    assert "PAPER_EVENT_UNQUALIFIED" in state.read()["latch_reasons"]


def test_status_subscription_targets_etf_and_does_not_infer_active():
    stream = Stream(
        [
            [{"T": "success", "msg": "connected"}],
            [{"T": "success", "msg": "authenticated"}],
            [{"T": "subscription", "statuses": ["SCHB"]}],
        ]
    )
    result = probe("fixture", "fixture", connector=lambda *a, **kw: stream, symbol="SCHB")
    assert stream.sent[-1] == {"action": "subscribe", "statuses": ["SCHB"]}
    assert result["status_subscription_acknowledged"]
    assert not result["initial_status_verified"]


def test_status_subscription_for_wrong_symbol_never_qualifies():
    stream = Stream(
        [
            [{"T": "success", "msg": "connected"}],
            [{"T": "success", "msg": "authenticated"}],
            [{"T": "subscription", "statuses": ["INTC"]}],
        ]
    )
    result = probe("fixture", "fixture", connector=lambda *a, **kw: stream, symbol="SCHB")
    assert not result["status_subscription_acknowledged"]


def test_current_cycle_builder_routes_quotes_to_etf(monkeypatch):
    from pathlib import Path

    import workers.paper_trial_observer as worker

    for name in (
        "AlpacaPaperAccountReader",
        "AlpacaPaperActivityReader",
        "AlpacaPaperQuoteReader",
        "NysePublishedCalendar",
        "PaperFillLedger",
    ):
        monkeypatch.setattr(worker, name, lambda *a, **kw: None)
    monkeypatch.setattr(worker, "observe_once", lambda **kw: kw["symbol"])
    root = Path(__file__).resolve().parents[1]
    cycle = worker.build_cycle(
        root, {"AIL_ALPACA_API_KEY": "fixture", "AIL_ALPACA_API_SECRET": "fixture"}, None
    )
    assert cycle() == "SCHB"
