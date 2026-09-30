"""Synthetic local-only opportunity pipeline and adversarial safety checks."""

import ast
from datetime import timedelta
from decimal import Decimal
from pathlib import Path

import pytest
from pydantic import ValidationError
from sqlalchemy import create_engine

from agents.long_term.models import (
    Claim,
    Freshness,
    PortfolioContext,
    ResearchAssessment,
    Source,
    ValuationContext,
)
from portfolio.state import ExperimentalAttribution
from portfolio.theses import MaterialEvent, PositionThesis, ThesisReview
from risk.evaluator import digest, evaluate
from risk.workflow import review_proposal
from strategies.engine import LongTermStrategy, SwingStrategy, concentration
from strategies.models import EntryConfig, StrategyVersion, SwingConfig
from strategies.opportunities import OpportunityEngine
from strategies.review import review_strategy_proposal
from strategies.service import OpportunityStrategyService
from strategies.storage import StrategyStore
from technical.indicators import SessionBar, SessionHistory, TechnicalIndicatorService
from tests.test_investment_policy import NOW, replace
from tests.test_investment_policy import inputs as original_inputs


@pytest.fixture
def context():
    policy, opening, state, _trade, switch = original_inputs.__wrapped__()
    claim = Claim(text="Fixture evidence", evidence_references=("source",))
    assessment = ResearchAssessment(
        assessment_id="assessment",
        run_id="research-run",
        scope_id="fixture",
        symbol="AAPL",
        timestamp=NOW,
        research_horizon="5-10+ years",
        current_price=100,
        price_currency="USD",
        market_data_timestamp=NOW,
        fundamental_data_timestamp=NOW,
        investment_thesis="Durable growth",
        thesis_status="UNCHANGED",
        positive_drivers=(claim,),
        negative_drivers=(claim,),
        risks=(claim,),
        catalysts=(claim,),
        invalidation_conditions=("Persistent deterioration",),
        valuation_context=ValuationContext(status="AVAILABLE", conclusions=(claim,)),
        data_sources=(
            Source(
                source_id="source",
                symbol="AAPL",
                source="Synthetic test",
                source_type="sec",
                published_at=NOW,
                retrieved_at=NOW,
                relevant_claim="Synthetic fixture",
                reliable=True,
                is_sample=True,
            ),
        ),
        data_quality={
            k: Freshness(state="CURRENT", as_of=NOW)
            for k in ("market", "fundamentals", "portfolio")
        },
        portfolio_fit=PortfolioContext(
            observation_id="observation", as_of=NOW, actual_symbols=(), current_allocation=0
        ),
        agent_summary="Fixture durable thesis; explicit opposing evidence",
        review_kind="baseline",
    )
    thesis = PositionThesis(
        account_id="fixture",
        symbol="AAPL",
        thesis_status="ACTIVE",
        current_thesis="Durable growth",
        last_review_date=NOW,
        agent_review_history=(
            ThesisReview(
                review_id="assessment", agent="research", reviewed_at=NOW, assessment="UNCHANGED"
            ),
        ),
    )
    version = StrategyVersion(
        strategy_id="durable-entry",
        strategy_version="0.1",
        strategy_domain="long_term",
        created_at=NOW,
        authorization_reference="synthetic-owner-review",
        configuration=EntryConfig(
            max_research_age_seconds=60,
            allow_test_data=True,
            valuation_decision="ACCEPTABLE",
            portfolio_fit_decision="ACCEPTABLE",
            fixed_notional=100,
        ),
    )
    return policy, opening, state, switch, assessment, thesis, version


def identify(context):
    p, _, s, _, a, t, v = context
    return OpportunityEngine().identify(
        a, t, s, p, v.configuration, now=NOW, domain=v.strategy_domain
    )


def strategy_result(context, *, history=None):
    p, _, s, _, a, t, v = context
    implementation = LongTermStrategy() if v.strategy_domain == "long_term" else SwingStrategy()
    return implementation.evaluate(
        identify(context), a, t, s, p, v, now=NOW, fees=Decimal(0), history=history
    )


def test_persisted_full_workflow_stops_at_human_review(context, tmp_path):
    p, o, s, k, a, t, v = context
    engine = create_engine("sqlite:///" + str(tmp_path / "strategy.db"))
    store = StrategyStore(engine)
    store.initialize()
    result = OpportunityStrategyService(store).run(a, t, o, s, p, v, k, now=NOW, fees=Decimal(0))
    assert result["evaluation"]["status"] == "RISK_REVIEW"
    assert result["review"]["status"] == "REQUIRE_HUMAN_REVIEW"
    assert not result["review"]["execution_available"]
    opportunity = store.opportunity(result["opportunity"]["opportunity_id"])
    assert opportunity.research_assessment_id == a.assessment_id
    assert opportunity.supporting_factors and opportunity.opposing_factors
    assert store.version(v.strategy_id, v.strategy_version) == v
    assert len(store.history(a.scope_id, a.symbol)) == 1
    assert result["events"][-1]["event"] == "human_review_required"
    assert all(e["timestamp"] and e["correlation_id"] for e in result["events"])
    engine.dispose()
    engine = create_engine("sqlite:///" + str(tmp_path / "strategy.db"))
    assert StrategyStore(engine).opportunity(opportunity.opportunity_id) == opportunity
    engine.dispose()


@pytest.mark.parametrize(
    "change",
    [
        {"timestamp": NOW - timedelta(days=1)},
        {"missing_data": ("fundamentals",)},
        {"data_sources": ()},
        {"market_data_timestamp": NOW + timedelta(seconds=1)},
        {"market_data_timestamp": None},
        {"risks": ()},
        {"invalidation_conditions": ()},
        {"data_quality": {}},
        {"portfolio_fit": None},
        {"price_currency": "EUR"},
        {"valuation_context": ValuationContext()},
    ],
)
def test_required_data_fails_closed(context, change):
    args = list(context)
    args[4] = replace(args[4], **change)
    assert strategy_result(args).status == "INSUFFICIENT_DATA"
    assert strategy_result(args).proposal is None


@pytest.mark.parametrize(
    "source_change",
    [
        {"reliable": False},
        {"retrieved_at": NOW + timedelta(seconds=1)},
        {"published_at": NOW - timedelta(days=200), "retrieved_at": NOW - timedelta(days=20)},
        {"symbol": "MSFT"},
    ],
)
def test_source_quality_checked_independently(context, source_change):
    args = list(context)
    args[4] = replace(args[4], data_sources=(replace(args[4].data_sources[0], **source_change),))
    assert strategy_result(args).proposal is None


def test_default_rejects_synthetic_data(context):
    args = list(context)
    args[6] = replace(args[6], configuration=replace(args[6].configuration, allow_test_data=False))
    assert strategy_result(args).status == "INSUFFICIENT_DATA"


@pytest.mark.parametrize("field", ["assessment", "thesis"])
def test_invalidated_thesis_exit_review_only(context, field):
    args = list(context)
    index = 4 if field == "assessment" else 5
    args[index] = replace(args[index], thesis_status="INVALIDATED")
    result = strategy_result(args)
    assert result.status == "EXIT_REVIEW" and result.proposal is None


def test_concentration_warning_never_sells(context):
    args = list(context)
    args[5] = replace(args[5], risk_flags=("CONCENTRATION_RISK",))
    result = strategy_result(args)
    assert result.status == "EXIT_REVIEW" and result.proposal is None


@pytest.mark.parametrize(
    "category",
    [
        "fundamental_deterioration",
        "competitive_deterioration",
        "management_failure",
        "valuation_dislocation",
        "better_capital_allocation",
        "catalyst_completed",
        "structural_industry_change",
    ],
)
def test_material_events_trigger_review_only(context, category):
    args = list(context)
    args[5] = replace(
        args[5],
        material_events=(
            MaterialEvent(
                event_id="event",
                occurred_at=NOW,
                category=category,
                source_reference="source",
                summary="Evidence-backed review",
            ),
        ),
    )
    assert strategy_result(args).status == "EXIT_REVIEW"


def test_unauthorized_existing_holding_does_not_authorize_add(context):
    from tests.test_portfolio_intelligence import holding

    args = list(context)
    args[0] = replace(args[0], new_purchase_allowlist=frozenset({"MSFT"}))
    args[2] = replace(args[2], positions=(holding("AAPL"),))
    opportunity = identify(args)
    assert "existing_holding" in opportunity.security_roles
    assert opportunity.opportunity_type == "ADD_TO_EXISTING"
    assert opportunity.opportunity_status == "REJECTED"
    assert strategy_result(args).status == "REJECTED"


def test_allowlist_is_independent_of_mag7_research(context):
    args = list(context)
    args[4] = replace(
        args[4], symbol="NVDA", data_sources=(replace(args[4].data_sources[0], symbol="NVDA"),)
    )
    args[5] = replace(args[5], symbol="NVDA")
    assert identify(args).opportunity_status == "REJECTED"
    args[0] = replace(args[0], new_purchase_allowlist=frozenset({"NVDA"}))
    assert strategy_result(args).proposal.trade.symbol == "NVDA"


def test_capital_and_concentration(context):
    result = strategy_result(context)
    proposal = result.proposal
    assert proposal.concentration_before == 0
    assert proposal.concentration_after == Decimal(100) / 160
    assert proposal.experimental_capital_required == 100
    args = list(context)
    args[6] = replace(args[6], configuration=replace(args[6].configuration, fixed_notional=10000))
    assert strategy_result(args).proposal.trade.quantity == 1
    p, o, s, k, _, _, _ = context
    expensive = replace(proposal.trade, quantity=2)
    checks = evaluate(p, o, s, expensive, k, now=NOW)
    assert not next(c for c in checks.checks if c.code == "experimental_capital").passed


def test_existing_portfolio_does_not_consume_experimental_capital(context):
    from tests.test_portfolio_intelligence import holding

    args = list(context)
    args[2] = replace(
        args[2],
        positions=(holding("MSFT"),),
        experimental_attribution=ExperimentalAttribution(
            baseline_id="reviewed-empty",
            source="owner",
            as_of=NOW,
            complete=True,
            account_ids=("fixture",),
            positions=(),
            open_orders=(),
        ),
    )
    result = strategy_result(args)
    assert result.proposal is not None and result.proposal.experimental_capital_required == 100


@pytest.mark.parametrize("values", [{"side": "sell"}, {"leverage_factor": 2}, {"quantity": -1}])
def test_short_leverage_rejected(context, values):
    p, o, s, k, _, _, _ = context
    proposal = strategy_result(context).proposal
    if values.get("quantity") == -1:
        with pytest.raises(ValidationError):
            replace(proposal.trade, **values)
    else:
        assert not evaluate(p, o, s, replace(proposal.trade, **values), k, now=NOW).allowed


def test_margin_rejected(context):
    p, o, s, k, _, _, _ = context
    s = replace(s, accounts=(replace(s.accounts[0], account_type="margin"),))
    result = evaluate(p, o, s, strategy_result(context).proposal.trade, k, now=NOW)
    assert not next(c for c in result.checks if c.code == "cash_accounts").passed


def test_news_cannot_enter_pipeline_and_no_broker_capability(context):
    with pytest.raises(TypeError, match="ResearchAssessment"):
        OpportunityEngine().identify(
            {"headline": "Buy now"},
            context[5],
            context[2],
            context[0],
            context[6].configuration,
            now=NOW,
        )
    for path in [*Path("strategies").glob("*.py"), Path("risk/proposals.py")]:
        tree = ast.parse(path.read_text())
        imports = [n.module or "" for n in ast.walk(tree) if isinstance(n, ast.ImportFrom)]
        assert not any(i.startswith(("integrations.brokers", "trading")) for i in imports)
        assert not any(
            isinstance(n, ast.Attribute)
            and n.attr in {"submit_order", "cancel_order", "replace_order"}
            for n in ast.walk(tree)
        )
    proposal = strategy_result(context).proposal
    assert not any(hasattr(proposal, n) for n in ("execute", "submit_order", "broker"))
    with pytest.raises(ValidationError):
        replace(proposal, status="APPROVED_FOR_LIVE")


def test_version_reproducibility_and_conflict(context, tmp_path):
    a = strategy_result(context).proposal
    b = strategy_result(context).proposal
    ignored = {"proposal_id", "proposal_digest", "opportunity_id"}
    assert a.model_dump(exclude=ignored) == b.model_dump(exclude=ignored)
    engine = create_engine("sqlite:///" + str(tmp_path / "versions.db"))
    store = StrategyStore(engine)
    store.initialize()
    store.register(context[6])
    with pytest.raises(ValueError, match="conflict"):
        store.register(
            replace(context[6], configuration=replace(context[6].configuration, fixed_notional=10))
        )
    engine.dispose()


def test_replay_catches_forged_proposal_even_with_valid_digest(context):
    p, o, s, k, a, t, v = context
    opportunity = identify(context)
    proposal = (
        LongTermStrategy().evaluate(opportunity, a, t, s, p, v, now=NOW, fees=Decimal(0)).proposal
    )
    forged = replace(proposal, confidence=1, trade=replace(proposal.trade, quantity=2))
    forged = replace(forged, proposal_digest=digest(forged.model_dump(exclude={"proposal_digest"})))
    result = review_strategy_proposal(p, o, s, forged, k, t, opportunity, a, v, now=NOW)
    assert result.status == "REJECT" and "strategy_replay_mismatch" in result.reasons
    assert review_proposal(p, o, s, proposal, k, t, now=NOW).status == "INSUFFICIENT_DATA"


def history(count=8):
    times = tuple(NOW - timedelta(days=count - i - 1) for i in range(count))
    return SessionHistory(
        symbol="AAPL",
        source="synthetic",
        calendar_id="fixture-explicit-sessions",
        sessions=times,
        adjustment="all",
        adjustment_known_at=times[0],
        reliable=True,
        is_sample=True,
        bars=tuple(
            SessionBar(
                session_close=t,
                available_at=t,
                open=100 + i,
                high=102 + i,
                low=99 + i,
                close=101 + i,
                volume=1000 + i,
            )
            for i, t in enumerate(times)
        ),
    )


def test_indicators_point_in_time_and_formulas():
    data = history()
    service = TechnicalIndicatorService()
    cutoff = data.sessions[-2]
    a = service.calculate(data, as_of=cutoff, period=3, allow_test_data=True)
    altered = replace(data, bars=(*data.bars[:-1], replace(data.bars[-1], high=10000, close=9999)))
    b = service.calculate(altered, as_of=cutoff, period=3, allow_test_data=True)
    assert a.values == b.values
    assert a.values["sma"] == 106 and a.values["ema"] == 106
    assert a.values["rsi"] == 100 and a.values["atr"] == 3
    assert a.values["drawdown"] == 0 and a.values["volume_average"] == 1005
    assert a.values["price_return"] == Decimal(107) / 104 - 1
    assert a.values["historical_volatility"] > 0
    relative = service.calculate(data, benchmark=data, as_of=NOW, period=3, allow_test_data=True)
    assert relative.values["relative_strength"] == 0


@pytest.mark.parametrize("kind", ["late_bar", "gap", "raw", "future_adjustment", "unreliable"])
def test_indicator_data_gates(kind):
    data = history()
    if kind == "late_bar":
        data = replace(
            data,
            bars=(*data.bars[:-1], replace(data.bars[-1], available_at=NOW + timedelta(seconds=1))),
        )
    elif kind == "gap":
        data = replace(data, bars=data.bars[1:])
    elif kind == "raw":
        data = replace(data, adjustment="raw")
    elif kind == "future_adjustment":
        data = replace(data, adjustment_known_at=NOW + timedelta(seconds=1))
    else:
        data = replace(data, reliable=False)
    result = TechnicalIndicatorService().calculate(data, as_of=NOW, period=3, allow_test_data=True)
    assert result.status == "INSUFFICIENT_DATA" and result.values["sma"] is None


def swing_version(version):
    return replace(
        version,
        strategy_id="swing-test",
        strategy_domain="swing",
        swing=SwingConfig(
            parameters_status="REVIEWED_FOR_RESEARCH",
            fast_period=2,
            slow_period=3,
            stop_atr_multiple=2,
            profit_atr_multiple=3,
            max_holding_sessions=5,
            max_holding_days=8,
            risk_budget=10,
            max_notional=100,
        ),
    )


def test_domains_separate_and_swing_unset(context):
    args = list(context)
    args[5] = replace(args[5], secondary_classifications=("SWING_ELIGIBLE",))
    args[6] = replace(args[6], strategy_domain="swing")
    assert strategy_result(args).reasons == ("swing_parameters_UNSET",)
    assert (
        LongTermStrategy()
        .evaluate(
            identify(args), args[4], args[5], args[2], args[0], args[6], now=NOW, fees=Decimal(0)
        )
        .status
        == "REJECTED"
    )
    args[6] = swing_version(args[6])
    proposal = strategy_result(args, history=history()).proposal
    assert proposal.strategy_domain == "swing" and proposal.expected_horizon == "Up to 5 sessions"
    assert "ATR" in proposal.proposed_entry
    assert not proposal.execution_available


@pytest.mark.parametrize(
    "price,sessions,reason",
    [(90, 0, "stop_loss"), (120, 0, "profit_target"), (100, 5, "maximum_holding_period")],
)
def test_swing_exit_rules_only_review(context, price, sessions, reason):
    result = SwingStrategy().review_exit(
        swing_version(context[6]),
        entry_price=Decimal(100),
        entry_atr=Decimal(3),
        current_price=Decimal(price),
        fast_sma=Decimal(101),
        slow_sma=Decimal(100),
        held_sessions=sessions,
        held_days=0,
    )
    assert result.status == "EXIT_REVIEW" and reason in result.reasons and result.proposal is None


@pytest.mark.parametrize(
    "field,value", [("valuation_decision", "UNATTRACTIVE"), ("portfolio_fit_decision", "REDUNDANT")]
)
def test_dimensions_remain_independent(context, field, value):
    args = list(context)
    args[6] = replace(args[6], configuration=replace(args[6].configuration, **{field: value}))
    opportunity = identify(args)
    assert opportunity.thesis_status == "UNCHANGED" and opportunity.supporting_factors
    assert strategy_result(args).status == "NO_ENTRY"


@pytest.mark.parametrize(
    "change",
    [
        {"authorization_reference": None},
        {"status": "RETIRED"},
        {"created_at": NOW + timedelta(seconds=1)},
    ],
)
def test_strategy_authorization_and_lifecycle(context, change):
    args = list(context)
    args[6] = replace(args[6], **change)
    assert strategy_result(args).proposal is None


def test_missing_policy_values_block_risk_without_defaulting(context, tmp_path):
    p, o, s, k, a, t, v = context
    engine = create_engine("sqlite:///" + str(tmp_path / "unset.db"))
    store = StrategyStore(engine)
    store.initialize()
    p = replace(p, max_daily_loss=None, max_experimental_loss=None, max_state_age_seconds=None)
    result = OpportunityStrategyService(store).run(a, t, o, s, p, v, k, now=NOW, fees=Decimal(0))
    assert result["review"]["status"] == "INSUFFICIENT_DATA"
    assert result["events"][-1]["event"] == "proposal_blocked"
    assert result["experimental_capital"]["remaining"] == "160"
    engine.dispose()


def test_open_orders_reduce_sizing_budget_and_increase_concentration(context):
    from portfolio.state import ExperimentalOrder
    from tests.test_investment_policy import order

    args = list(context)
    pending = order(symbol="AAPL", quantity=1, filled_quantity=0, limit_price=70, remaining_fees=0)
    args[2] = replace(
        args[2],
        open_orders=(pending,),
        experimental_attribution=replace(
            args[2].experimental_attribution,
            open_orders=(
                ExperimentalOrder(
                    account_id="fixture", order_id=pending.order_id, strategy_id="durable-entry"
                ),
            ),
        ),
    )
    assert strategy_result(args).proposal is None
    before, after = concentration(args[2], "AAPL", Decimal(50), Decimal(1))
    assert before == 0 and after == Decimal(120) / 159


def test_long_term_does_not_exit_on_price_volatility(context):
    args = list(context)
    args[4] = replace(args[4], current_price=50)
    proposal = strategy_result(args).proposal
    assert proposal is not None and proposal.expected_horizon == "5-10+ years"
    assert "stop" not in proposal.proposed_exit_logic.lower()


def test_calendar_holidays_early_closes_and_out_of_calendar_bar():
    from datetime import UTC, datetime

    data = history(4)
    sessions = tuple(
        datetime(2026, 7, d, h, tzinfo=UTC) for d, h in ((1, 20), (2, 17), (6, 20), (7, 20))
    )
    bars = tuple(replace(b, session_close=t, available_at=t) for b, t in zip(data.bars, sessions))
    data = replace(data, sessions=sessions, bars=bars, adjustment_known_at=sessions[0])
    result = TechnicalIndicatorService().calculate(
        data, as_of=sessions[-1], period=2, allow_test_data=True
    )
    assert result.status == "AVAILABLE"
    with pytest.raises(ValidationError, match="calendar"):
        replace(data, sessions=sessions[:-1])


def test_stale_thesis_binding_and_unknown_evidence_block(context):
    args = list(context)
    args[5] = replace(args[5], agent_review_history=())
    assert strategy_result(args).status == "INSUFFICIENT_DATA"
    args = list(context)
    args[4] = replace(args[4], risks=(Claim(text="Unknown", evidence_references=("missing",)),))
    assert strategy_result(args).status == "INSUFFICIENT_DATA"


def test_expired_opportunity_cannot_enter(context):
    p, _, s, _, a, t, v = context
    expired = replace(identify(context), opportunity_status="EXPIRED")
    assert (
        LongTermStrategy().evaluate(expired, a, t, s, p, v, now=NOW, fees=Decimal(0)).status
        == "REJECTED"
    )


def test_failed_persistence_does_not_return_success(context, tmp_path):
    from sqlalchemy import event

    p, o, s, k, a, t, v = context
    engine = create_engine("sqlite:///" + str(tmp_path / "rollback.db"))
    store = StrategyStore(engine)
    store.initialize()

    def reject_insert(conn, cursor, statement, parameters, execution_context, executemany):
        if statement.startswith("INSERT INTO opportunity_evaluations_v1"):
            raise RuntimeError("Synthetic persistence failure")

    event.listen(engine, "before_cursor_execute", reject_insert)
    with pytest.raises(RuntimeError, match="Synthetic persistence"):
        OpportunityStrategyService(store).run(a, t, o, s, p, v, k, now=NOW, fees=Decimal(0))
    assert store.history(a.scope_id, a.symbol) == ()
    engine.dispose()


def test_legacy_proposal_digest_compatibility_is_limited_to_default_metadata(context):
    from risk.proposals import (
        OpportunityProposalFields,
        create_trade_proposal,
        proposal_binding_valid,
    )
    from tests.test_policy_v02 import active_thesis, details

    p, _, _, trade, _ = original_inputs.__wrapped__()
    proposal = create_trade_proposal(p, trade, details(active_thesis()), now=NOW)
    payload = proposal.model_dump(
        exclude={"proposal_digest", *OpportunityProposalFields.model_fields}
    )
    legacy = replace(proposal, proposal_digest=digest(payload))
    assert proposal_binding_valid(legacy)
    assert not proposal_binding_valid(replace(legacy, opportunity_id="unbound"))
