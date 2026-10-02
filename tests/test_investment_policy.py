import json
import logging
import sqlite3
from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest
from pydantic import ValidationError

from portfolio.reconciliation import reconcile
from portfolio.repository import PortfolioRepository
from portfolio.state import (
    ExperimentalAttribution,
    PortfolioState,
    StateOrder,
    StatePosition,
    Transaction,
)
from risk.evaluator import HypotheticalTrade, KillSwitch, evaluate
from risk.policy import InvestmentPolicy

NOW = datetime(2026, 9, 29, 15, tzinfo=UTC)


def replace(model, **changes):
    return type(model).model_validate(model.model_dump() | changes)


def attribute(state):
    """Explicit test-only classification of the fixture inventory as experimental."""
    return replace(
        state,
        experimental_attribution=ExperimentalAttribution(
            baseline_id="fixture-baseline",
            source="test-owner-review",
            as_of=state.as_of,
            complete=True,
            account_ids=tuple(a.account_id for a in state.accounts),
            positions=tuple(
                {
                    "account_id": p.account_id,
                    "symbol": p.symbol,
                    "quantity": p.quantity,
                    "cost_basis": p.cost_basis,
                }
                for p in state.positions
            ),
            open_orders=tuple(
                {"account_id": o.account_id, "order_id": o.order_id} for o in state.open_orders
            ),
        ),
    )


@pytest.fixture
def inputs():
    account = {
        "account_id": "fixture",
        "currency": "USD",
        "account_type": "cash",
        "cash": "160",
        "settled_cash": "160",
        "unsettled_cash": "0",
        "buying_power": "160",
        "cash_basis": "before_reservations",
    }
    opening = PortfolioState(
        source="synthetic-fixture",
        environment="research",
        as_of=NOW - timedelta(minutes=1),
        history_start=NOW - timedelta(minutes=2),
        accounts_complete=True,
        positions_complete=True,
        orders_complete=True,
        transactions_complete=True,
        accounts=(account,),
        positions=(),
        open_orders=(),
        transactions=(),
    )
    closing = replace(
        opening,
        as_of=NOW,
        history_start=opening.as_of,
        daily_pnl="0",
        experimental_pnl="0",
        daily_pnl_start=NOW.replace(hour=0),
        daily_pnl_as_of=NOW,
    )
    # Explicit test-only choices; these are not owner policy defaults.
    policy = InvestmentPolicy(
        max_daily_loss="10",
        max_experimental_loss="20",
        max_state_age_seconds=60,
        daily_loss_timezone="UTC",
    )
    trade = HypotheticalTrade(
        account_id="fixture",
        symbol="AAPL",
        side="buy",
        quantity="1",
        limit_price="100",
        estimated_fees="0",
        asset_type="equity",
        leverage_factor="1",
        thesis="Fixture research rationale",
        entry_thesis="Fixture entry rationale",
        exit_invalidation_thesis="Fixture invalidation rationale",
    )
    return policy, opening, attribute(closing), trade, KillSwitch(enabled=False, as_of=NOW)


def run(args):
    return evaluate(*args, now=NOW)


def rejected(result):
    return {c.code for c in result.checks if not c.passed}


def order(**changes):
    return StateOrder.model_validate(
        {
            "account_id": "fixture",
            "order_id": "order-1",
            "symbol": "MSFT",
            "side": "buy",
            "quantity": "2",
            "filled_quantity": "1",
            "limit_price": "50",
            "remaining_fees": "1",
            "status": "pending_cancel",
            "asset_type": "equity",
            "leverage_factor": "1",
            "order_type": "limit",
            "time_in_force": "day",
            "session": "core",
            "complex": False,
        }
        | changes
    )


def test_defaults_fail_closed_and_schema(inputs):
    result = run((InvestmentPolicy(), *inputs[1:]))
    assert not result.allowed and not result.execution_available
    assert {
        "configured_max_daily_loss",
        "configured_max_state_age_seconds",
        "configured_daily_loss_timezone",
    } <= rejected(result)
    assert InvestmentPolicy.model_json_schema()["properties"]["max_daily_loss"]["default"] is None


@pytest.mark.parametrize(
    "changes",
    [
        {"production_trading": True},
        {"automated_trading": True},
        {"environment": "production"},
        {"human_approval_required": False},
        {"margin_allowed": True},
        {"options_allowed": True},
        {"kill_switch_required": False},
        {"fractional_orders_allowed": True},
        {"max_total_exposure": "161"},
        {"max_experimental_capital": "161"},
        {"max_daily_loss": "NaN"},
        {"max_daily_loss": "-1"},
        {"unknown_control": True},
    ],
)
def test_unsafe_policy_rejected(changes):
    with pytest.raises(ValidationError):
        InvestmentPolicy(**changes)


def test_allowed_is_deterministic_and_audited(inputs, caplog):
    with caplog.at_level(logging.INFO, logger="investment_policy.audit"):
        first, second = run(inputs), run(inputs)
    assert first == second and first.allowed and not first.execution_available
    event = json.loads(caplog.records[0].message)
    assert event["allowed"] and event["input_digest"] == first.input_digest
    assert "fixture" not in caplog.text
    assert all(check.explanation for check in first.checks)


@pytest.mark.parametrize(
    "changes",
    [
        {"symbol": "TSLA"},
        {"side": "sell"},
        {"quantity": "0.5"},
        {"asset_type": "option"},
        {"leverage_factor": "2"},
        {"complex": True},
        {"order_type": "market"},
        {"time_in_force": "gtc"},
        {"session": "overnight"},
        {"currency": "EUR"},
    ],
)
def test_forbidden_proposals(inputs, changes):
    policy, opening, state, trade, switch = inputs
    assert "proposed_order" in rejected(
        run((policy, opening, state, replace(trade, **changes), switch))
    )


@pytest.mark.parametrize(
    "field,value,code",
    [
        ("estimated_fees", None, "known_fees"),
        ("limit_price", "161", "experimental_capital"),
        ("account_id", "other", "settled_cash"),
    ],
)
def test_proposal_limits(inputs, field, value, code):
    p, o, s, t, k = inputs
    assert code in rejected(run((p, o, s, replace(t, **{field: value}), k)))


def test_open_orders_reserve_remaining_quantity_and_fees(inputs):
    p, o, s, t, k = inputs
    s = attribute(replace(s, open_orders=(order(),)))
    assert reconcile(o, s).open_buy_commitment == Decimal(51)
    assert run((p, o, s, t, k)).allowed
    t = replace(t, limit_price="110")
    assert {"experimental_capital", "settled_cash"} <= rejected(run((p, o, s, t, k)))
    s = replace(s, open_orders=(order(remaining_fees=None),))
    assert not run((p, o, s, t, k)).allowed


def test_settlement_and_partial_fill_reconciliation(inputs):
    p, o, s, t, k = inputs
    tx = Transaction(
        account_id="fixture",
        transaction_id="fill-1",
        posted_at=NOW,
        currency="USD",
        kind="fill",
        symbol="AAPL",
        quantity_delta="1",
        cash_delta="-51",
        settled_delta="-51",
        unsettled_delta="0",
    )
    position = StatePosition(
        account_id="fixture",
        symbol="AAPL",
        quantity="1",
        price="50",
        price_as_of=NOW,
        cost_basis="51",
        asset_type="equity",
        leverage_factor="1",
    )
    s = replace(
        s,
        accounts=(replace(s.accounts[0], cash="109", settled_cash="109"),),
        transactions=(tx,),
        positions=(position,),
    )
    report = reconcile(o, s)
    assert report.passed and report.gross_exposure == 50
    assert report.cash_allocation == Decimal(109) / 159
    assert report.concentration == 1 and report.per_symbol == {"AAPL": Decimal(50)}
    assert run((p, o, s, t, k)).allowed
    assert "position_ledger_mismatch" in reconcile(o, replace(s, positions=())).reasons
    assert "cash_ledger_mismatch" in reconcile(o, replace(s, transactions=())).reasons


def test_unsettled_cash_and_buying_power_never_replace_settled_cash(inputs):
    p, o, s, t, k = inputs
    a = replace(s.accounts[0], settled_cash="20", unsettled_cash="140", buying_power="1000")
    o, s = replace(o, accounts=(a,)), replace(s, accounts=(a,))
    assert reconcile(o, s).passed
    assert "settled_cash" in rejected(run((p, o, s, t, k)))
    a = replace(a, settled_cash=None)
    assert not reconcile(replace(o, accounts=(a,)), replace(s, accounts=(a,))).passed


@pytest.mark.parametrize(
    "changes,reason",
    [
        ({"orders_complete": False}, "incomplete_snapshot"),
        ({"transactions_complete": False}, "incomplete_snapshot"),
        ({"history_start": NOW}, "transaction_window_mismatch"),
        ({"environment": "paper"}, "source_or_environment_changed"),
        ({"accounts": ()}, "account_scope_changed"),
        ({"open_orders": (order(), order())}, "duplicate_order"),
        ({"open_orders": (order(account_id="unknown"),)}, "unknown_account_reference"),
        ({"open_orders": (order(status="unknown"),)}, "unknown_order_status"),
    ],
)
def test_inconsistent_imports(inputs, changes, reason):
    _, o, s, _, _ = inputs
    report = reconcile(o, replace(s, **changes))
    assert not report.passed and reason in report.reasons


@pytest.mark.parametrize("pnl", ["-10", "-11", None])
def test_daily_loss_stop_inclusive(inputs, pnl):
    p, o, s, t, k = inputs
    assert "daily_loss" in rejected(run((p, o, replace(s, daily_pnl=pnl), t, k)))


def test_daily_window_and_freshness(inputs):
    p, o, s, t, k = inputs
    assert "daily_loss" in rejected(run((p, o, replace(s, daily_pnl_start=o.as_of), t, k)))
    assert "daily_loss" in rejected(
        run((replace(p, daily_loss_timezone="Invalid/Zone"), o, s, t, k))
    )
    for now in (NOW + timedelta(seconds=61), NOW - timedelta(seconds=1)):
        assert "fresh_state" in rejected(evaluate(*inputs, now=now))
    for switch in (
        KillSwitch(),
        KillSwitch(enabled=True, as_of=NOW),
        KillSwitch(enabled=False, as_of=NOW - timedelta(hours=1)),
    ):
        assert "kill_switch" in rejected(run((p, o, s, t, switch)))


def test_optional_caps_and_unknown_buying_power(inputs):
    p, o, s, t, k = inputs
    assert "concentration_limit" in rejected(run((replace(p, max_concentration="0.5"), o, s, t, k)))
    assert "position_limit" in rejected(run((replace(p, max_position_exposure="99"), o, s, t, k)))
    s = replace(s, accounts=(replace(s.accounts[0], buying_power=None),))
    assert "buying_power" in rejected(run((p, o, s, t, k)))


def test_durable_evidence_and_idempotency(inputs, tmp_path):
    path = tmp_path / "portfolio.sqlite"
    repo = PortfolioRepository(path)
    evidence = repo.evaluate_and_record(*inputs, now=NOW)
    repo.evaluate_and_record(*inputs, now=NOW)
    assert PortfolioRepository(path).get(evidence.evaluation.input_digest) == evidence
    with sqlite3.connect(path) as connection:
        assert connection.execute("SELECT count(*) FROM portfolio_evidence_v4").fetchone()[0] == 1
        connection.execute("UPDATE portfolio_evidence_v4 SET checksum = 'damaged'")
    with pytest.raises(ValueError, match="checksum"):
        repo.get(evidence.evaluation.input_digest)


def test_capital_does_not_shrink_with_market_loss(inputs):
    p, o, s, t, k = inputs
    position = StatePosition(
        account_id="fixture",
        symbol="MSFT",
        quantity="1",
        price="10",
        price_as_of=o.as_of,
        cost_basis="150",
        asset_type="equity",
        leverage_factor="1",
    )
    o, s = replace(o, positions=(position,)), replace(s, positions=(position,))
    s = attribute(s)
    result = run((p, o, s, t, k))
    assert result.projected_exposure == 110 and result.projected_capital == 250
    assert "experimental_capital" in rejected(result)
    s = replace(s, experimental_attribution=None)
    assert "experimental_attribution" in rejected(run((p, o, s, t, k)))


def test_settlement_transfer_and_duplicate_transactions(inputs):
    _, o, s, _, _ = inputs
    a = replace(o.accounts[0], settled_cash="60", unsettled_cash="100")
    o = replace(o, accounts=(a,))
    tx = Transaction(
        account_id="fixture",
        transaction_id="settlement-1",
        posted_at=NOW,
        currency="USD",
        kind="settlement",
        cash_delta="0",
        settled_delta="100",
        unsettled_delta="-100",
    )
    s = replace(s, transactions=(tx,))
    assert reconcile(o, s).passed
    assert "duplicate_transaction" in reconcile(o, replace(s, transactions=(tx, tx))).reasons
    assert (
        "transaction_outside_window"
        in reconcile(o, replace(s, transactions=(replace(tx, posted_at=o.as_of),))).reasons
    )
    assert (
        "unverified_settled_cash"
        in reconcile(o, replace(s, transactions=(replace(tx, settled_delta=None),))).reasons
    )


def test_multi_account_funding_is_not_pooled(inputs):
    p, o, s, t, k = inputs
    first = replace(o.accounts[0], cash="60", settled_cash="60", buying_power="1000")
    second = replace(o.accounts[0], account_id="second", cash="100", settled_cash="100")
    o, s = replace(o, accounts=(first, second)), replace(s, accounts=(first, second))
    assert reconcile(o, s).settled_cash == 160
    assert "settled_cash" in rejected(run((p, o, s, t, k)))
    s = attribute(replace(s, open_orders=(order(account_id="second", quantity="3"),)))
    assert "experimental_capital" in rejected(run((p, o, s, t, k)))


@pytest.mark.parametrize(
    "changes,code",
    [
        ({"account_type": "margin"}, "cash_accounts"),
        ({"cash_basis": "unknown"}, "cash_semantics"),
        ({"currency": "EUR"}, "reconciled"),
        ({"settled_cash": "-1", "unsettled_cash": "161"}, "cash_components"),
        ({"buying_power": "99"}, "buying_power"),
    ],
)
def test_account_controls(inputs, changes, code):
    p, o, s, t, k = inputs
    a = replace(o.accounts[0], **changes)
    assert code in rejected(run((p, replace(o, accounts=(a,)), replace(s, accounts=(a,)), t, k)))


@pytest.mark.parametrize(
    "changes",
    [
        {"side": "sell"},
        {"complex": True},
        {"filled_quantity": "0.5"},
        {"asset_type": "option"},
        {"leverage_factor": "2"},
    ],
)
def test_existing_order_policy(inputs, changes):
    p, o, s, t, k = inputs
    assert "existing_orders" in rejected(
        run((p, o, attribute(replace(s, open_orders=(order(**changes),))), t, k))
    )


def test_bad_numeric_and_timestamp_inputs(inputs):
    _, _, s, t, _ = inputs
    for value in ("NaN", "Infinity", "-1", "0"):
        with pytest.raises(ValidationError):
            replace(t, quantity=value)
    with pytest.raises(ValidationError):
        replace(s, as_of=NOW.replace(tzinfo=None))
    with pytest.raises(ValueError, match="timezone"):
        evaluate(*inputs, now=NOW.replace(tzinfo=None))
    assert InvestmentPolicy(new_purchase_allowlist={"TSLA"}).new_purchase_allowlist == {"TSLA"}


def test_initial_policy_and_schema_are_current():
    from pathlib import Path

    root = Path(__file__).resolve().parents[1]
    assert (
        InvestmentPolicy.model_validate_json(
            (root / "docs/investment-policy.initial.json").read_text()
        )
        == InvestmentPolicy()
    )
    assert json.loads((root / "docs/investment-policy.schema.json").read_text()) == (
        InvestmentPolicy.model_json_schema()
    )


def test_rejected_decision_is_persisted(inputs, tmp_path):
    repo = PortfolioRepository(tmp_path / "evidence.sqlite")
    evidence = repo.evaluate_and_record(InvestmentPolicy(), *inputs[1:], now=NOW)
    assert not evidence.evaluation.allowed
    assert repo.get(evidence.evaluation.input_digest) == evidence


def test_order_identity_and_fill_progression(inputs):
    _, o, s, _, _ = inputs
    o = replace(o, open_orders=(order(),))
    assert (
        "order_fill_regression"
        in reconcile(o, replace(s, open_orders=(order(filled_quantity="0"),))).reasons
    )
    assert (
        "order_identity_changed"
        in reconcile(o, replace(s, open_orders=(order(symbol="AAPL"),))).reasons
    )
    assert (
        "inconsistent_order_status"
        in reconcile(o, replace(s, open_orders=(order(filled_quantity="2"),))).reasons
    )


def test_owner_cap_revision_and_funding_gate(inputs):
    from pathlib import Path
    from risk.policy import load_investment_policy

    policy = load_investment_policy(Path("conf/investment-policy-v03.json"))
    assert policy.policy_revision == "0.3"
    assert policy.agent_experimental_capital_limit == Decimal("1000")
    assert not policy.production_trading and not policy.automated_trading
    with pytest.raises(ValidationError):
        InvestmentPolicy(policy_revision="0.3", agent_experimental_capital_limit="1000.01")
    with pytest.raises(ValidationError):
        InvestmentPolicy(policy_revision="0.2", agent_experimental_capital_limit="1000")
    # Higher cap cannot create settled cash or fill unset risk controls.
    trade = replace(inputs[3], limit_price="500")
    result = run((replace(inputs[0], policy_revision="0.3",
                          agent_experimental_capital_limit="1000"),
                  inputs[1], inputs[2], trade, inputs[4]))
    assert "settled_cash" in rejected(result)
    assert not result.allowed and not result.execution_available
    defaults = run((policy, *inputs[1:]))
    assert not defaults.allowed and not defaults.execution_available
