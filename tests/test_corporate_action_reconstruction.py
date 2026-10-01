"""Economic accounting and historical availability remain separate."""

from dataclasses import replace
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal

import httpx
import pytest

from experiment_lab.corporate_action_reconstruction import (
    SECURITIES,
    CorporateActionRepository,
    EconomicState,
    KnowledgeState,
    LedgerEvent,
    SourceTermEvidence,
    account_returns,
    adjusted_bars,
    compare_source_terms,
    economic_state,
    knowledge_state,
    normalize_alpaca_event,
    qualify_gates,
    reconcile,
)
from experiment_lab.corporate_action_snapshot import capture
from experiment_lab.corporate_actions import AlpacaCorporateActionProvider
from experiment_lab.historical_records import RawHistoricalPriceBar

AT = datetime(2024, 6, 1, tzinfo=UTC)


def event(symbol="NVDA", kind="FORWARD_SPLIT", ex=date(2024, 6, 10), *,
          ratio="10", amount=None, pay=None, verified=True, published=None):
    return LedgerEvent(
        security_id=SECURITIES[symbol], source_symbol=symbol, event_type=kind,
        provider="source-a", source_event_id=f"{symbol}-{kind}-{ex}",
        declaration_date=date(2024, 5, 22), publication_at=published,
        publication_proven=published is not None, ex_date=ex, record_date=None,
        payment_date=pay, effective_date=ex,
        amount=Decimal(amount) if amount is not None else None,
        ratio=Decimal(ratio) if "SPLIT" in kind else None,
        currency="USD" if "DIVIDEND" in kind else None,
        retrieved_at=AT + timedelta(days=365), raw_source_reference="source-a/1",
        source_digest="a" * 64, terms_verified=verified,
        data_quality="TERMS_CORROBORATED" if verified else "UNVERIFIED",
    )


def bar(day, price, symbol="NVDA"):
    return RawHistoricalPriceBar(
        symbol=symbol, timestamp=datetime.combine(day, datetime.min.time(), UTC),
        open=Decimal(price), high=Decimal(price), low=Decimal(price),
        close=Decimal(price), volume=Decimal(100), feed="iex", adjustment_mode="raw",
        retrieved_at=AT + timedelta(days=365), provider="Alpaca", source_digest="b" * 64,
    )


def test_forward_and_reverse_split_preserve_value_and_raw_bar():
    raw = (bar(date(2024, 6, 7), "100"), bar(date(2024, 6, 10), "10"))
    original = raw[0].model_dump()
    split = event()
    output = adjusted_bars(raw, (split,), coverage_complete=True)
    assert [row["close"] for row in output["series"]] == ["10", "10"]
    assert [row["volume"] for row in output["series"]] == ["1000", "100"]
    assert account_returns(raw, (split,), coverage_complete=True)["total_return"] == "0"
    assert raw[0].model_dump() == original
    reverse = event(kind="REVERSE_SPLIT", ratio="0.1")
    reverse_raw = (bar(date(2024, 6, 7), "10"), bar(date(2024, 6, 10), "100"))
    assert account_returns(reverse_raw, (reverse,), coverage_complete=True)[
        "series"][-1]["shares"] == "0.1"


def test_regular_and_special_dividend_ex_entitlement_payment_and_reinvestment():
    days = (date(2024, 6, 7), date(2024, 6, 10), date(2024, 6, 11))
    raw = tuple(bar(day, price) for day, price in zip(days, ("100", "99", "99"), strict=True))
    dividend = event(kind="REGULAR_DIVIDEND", ex=days[1], ratio="0",
                     amount="1", pay=days[2])
    cash = account_returns(raw, (dividend,), coverage_complete=True, sessions=days)
    assert cash["series"][1]["cash"] == "0"
    assert cash["series"][1]["dividend_receivable"] == "1"
    assert cash["series"][2]["cash"] == "1"
    assert cash["price_return"] == "-0.01" and cash["total_return"] == "0"
    assert account_returns(raw, (dividend,), coverage_complete=True, reinvest=True)[
        "series"][-1]["cash"] == "0"
    special = replace(dividend, event_type="SPECIAL_DIVIDEND", source_event_id="special",
                      amount=Decimal(2))
    both = account_returns(raw, (dividend, special), coverage_complete=True)
    assert both["series"][-1]["cash"] == "3"
    with pytest.raises(ValueError, match="Duplicate"):
        account_returns(raw, (dividend, dividend), coverage_complete=True)


def test_missing_dividend_terms_sessions_and_conflicts_fail_closed():
    raw = (bar(date(2024, 6, 7), "100"), bar(date(2024, 6, 10), "99"))
    dividend = event(kind="REGULAR_DIVIDEND", ratio="0", amount="1",
                     pay=date(2024, 6, 11))
    assert account_returns(raw, (dividend,), coverage_complete=False)[
        "status"] == "INSUFFICIENT_DATA"
    assert account_returns(raw, (replace(dividend, terms_verified=False),),
                           coverage_complete=True)["status"] == "INSUFFICIENT_DATA"
    assert account_returns(raw, (dividend,), coverage_complete=True,
                           sessions=(date(2024, 6, 7),))["reason"] == "MISSING_OR_MISALIGNED_SESSIONS"
    other = replace(dividend, provider="source-b", amount=Decimal("1.1"))
    assert reconcile((dividend,), (other,))["conflicts"] == [dividend.event_key]
    assert reconcile((dividend,), ())["missing_secondary"] == [dividend.event_key]
    missing_payment = (bar(date(2024, 6, 7), "100"),
                       bar(date(2024, 6, 10), "99"), bar(date(2024, 6, 12), "99"))
    assert account_returns(missing_payment, (dividend,), coverage_complete=True)[
        "reason"] == "MISSING_PAYMENT_SESSION"


def test_publication_and_economic_states_are_independent():
    split = event(published=datetime(2024, 5, 22, 20, tzinfo=UTC))
    assert knowledge_state(split, datetime(2024, 5, 22, 19, tzinfo=UTC)) == (
        KnowledgeState.EVENT_NOT_YET_KNOWN_AT_T)
    assert knowledge_state(split, datetime(2024, 6, 1, tzinfo=UTC)) == (
        KnowledgeState.EVENT_KNOWN_AT_T)
    assert economic_state(split, date(2024, 6, 9)) == EconomicState.EVENT_NOT_YET_EFFECTIVE
    assert economic_state(split, date(2024, 6, 10)) == EconomicState.EVENT_ECONOMICALLY_EFFECTIVE
    unknown = replace(split, publication_at=None, publication_proven=False)
    assert knowledge_state(unknown, AT) == KnowledgeState.EVENT_AVAILABILITY_UNCERTAIN
    assert economic_state(replace(split, terms_verified=False), date(2024, 6, 10)) == (
        EconomicState.EVENT_TERMS_UNVERIFIED)


def test_versions_duplicate_conflict_and_distinct_alphabet_share_classes():
    repo = CorporateActionRepository()
    original = event()
    repo.add(original)
    repo.add(original)
    corrected = replace(original, event_version=2, supersedes=original.event_key,
                        ratio=Decimal(5))
    repo.add(corrected)
    assert repo.current() == (corrected,)
    assert len(repo.all_versions()) == 2
    with pytest.raises(ValueError, match="Conflicting duplicate"):
        repo.add(replace(original, ratio=Decimal(3)))
    goog = event(symbol="GOOG")
    googl = event(symbol="GOOGL")
    assert goog.security_id != googl.security_id
    assert normalize_alpaca_event("forward_splits", {"symbol": "GOOG", "ex_date":
        "2022-07-18", "old_rate": 1, "new_rate": 20, "id": "g"}, AT).security_id == SECURITIES["GOOG"]


def test_alpaca_nested_feed_and_oos_refusal():
    def handler(request):
        return httpx.Response(200, json={"corporate_actions": {"cash_dividends": [
            {"id": "a", "symbol": "AAPL", "ex_date": "2025-05-12", "rate": 0.26,
             "payable_date": "2025-05-15"}]}, "next_page_token": None})

    provider = AlpacaCorporateActionProvider("fake", "fake", transport=httpx.MockTransport(handler))
    rows = provider.actions(("AAPL",), date(2025, 5, 1), date(2025, 5, 31))
    assert len(rows) == 1 and rows[0].action_type == "cash_dividends"
    assert rows[0].announced_at is None
    with pytest.raises(ValueError):
        provider.actions(("AAPL",), date(2025, 12, 1), date(2026, 1, 1))
    with pytest.raises(ValueError, match="OOS"):
        event(ex=date(2026, 1, 2))


def test_qualifying_gate_does_not_promote_exploratory_accounting():
    arguments = dict.fromkeys(("provenance", "terms", "splits_complete",
                               "distributions_complete", "availability", "effective_dates",
                               "versions", "reproducible", "raw_immutable",
                               "independent_reconciliation", "benchmark_consistent",
                               "no_lookahead", "oos_sealed"), True)
    arguments["availability"] = False
    gates = qualify_gates(**arguments)
    assert gates["historical_accounting"] == "PASS"
    assert gates["historical_research_signal"] == "FAIL"
    arguments["distributions_complete"] = False
    assert qualify_gates(**arguments)["historical_accounting"] == "FAIL"


def test_issuer_evidence_partial_terms_do_not_become_verified():
    dividend = event(kind="REGULAR_DIVIDEND", ratio="0", amount="1",
                     pay=date(2024, 6, 11))
    source = SourceTermEvidence(dividend.security_id, dividend.event_type,
                                "issuer", "c" * 64, "issuer/page",
                                payment_date=date(2024, 6, 11), amount=Decimal(1))
    assert compare_source_terms(dividend, source)["status"] == "PARTIAL"
    assert compare_source_terms(dividend, replace(source, ex_date=date(2024, 6, 9)))[
        "status"] == "CONFLICT"


def test_voo_price_cash_and_reinvested_returns_are_named_separately():
    days = (date(2025, 3, 26), date(2025, 3, 27), date(2025, 3, 31))
    raw = tuple(bar(day, price, "VOO") for day, price in zip(
        days, ("100", "98", "99"), strict=True))
    distribution = event(symbol="VOO", kind="REGULAR_DIVIDEND", ex=days[1],
                         ratio="0", amount="2", pay=days[2])
    retained = account_returns(raw, (distribution,), coverage_complete=True)
    reinvested = account_returns(raw, (distribution,), coverage_complete=True, reinvest=True)
    assert retained["price_return"] == "-0.01"
    assert retained["total_return"] == "0.01"
    assert retained["methodology"] == "TOTAL_RETURN_CASH_DIVIDENDS"
    assert reinvested["methodology"] == "TOTAL_RETURN_REINVESTED"
    assert reinvested["series"][-1]["cash"] == "0"
    assert retained["qualifying_validation"] is False


def test_action_snapshot_is_immutable_and_rejects_oos_response(tmp_path):
    env = tmp_path / "alpaca.env"
    env.write_text("AIL_ALPACA_API_KEY=fake\nAIL_ALPACA_API_SECRET=fake\n")
    output = tmp_path / "actions.json"

    def handler(request):
        assert request.headers["APCA-API-KEY-ID"] == "fake"
        return httpx.Response(200, json={"corporate_actions": {"cash_dividends": [
            {"symbol": "AAPL", "ex_date": "2025-05-12", "payable_date": "2025-05-15",
             "rate": 0.26}]}, "next_page_token": None})

    manifest = capture(env, output, date(2025, 5, 1), date(2025, 5, 31), ("AAPL",),
                       transport=httpx.MockTransport(handler))
    assert manifest["complete_coverage_proven"] is False
    assert output.exists()
    with pytest.raises(ValueError, match="already exists"):
        capture(env, output, date(2025, 5, 1), date(2025, 5, 31), ("AAPL",),
                transport=httpx.MockTransport(handler))
    with pytest.raises(ValueError):
        capture(env, tmp_path / "oos.json", date(2025, 12, 1), date(2026, 1, 1),
                ("AAPL",), transport=httpx.MockTransport(handler))

    def future_handler(request):
        return httpx.Response(200, json={"corporate_actions": {"cash_dividends": [
            {"symbol": "AAPL", "ex_date": "2026-01-02"}]}})

    forbidden = tmp_path / "future-response.json"
    with pytest.raises(ValueError, match="OOS"):
        capture(env, forbidden, date(2025, 5, 1), date(2025, 5, 31), ("AAPL",),
                transport=httpx.MockTransport(future_handler))
    assert not forbidden.exists()
