"""Synthetic-only v0.9 risk snapshots; never use with broker state."""

from datetime import UTC, datetime, timedelta

from portfolio.state import (
    ExperimentalAttribution,
    ExperimentalOrder,
    ExperimentalPosition,
    PortfolioState,
    StateOrder,
    StatePosition,
)
from risk.diagnostic_harness import DiagnosticInput
from risk.evaluator import HypotheticalTrade, KillSwitch
from risk.policy import InvestmentPolicy

NOW = datetime(2026, 9, 30, 15, tzinfo=UTC)


def scenarios() -> dict[str, DiagnosticInput]:
    account = {
        "account_id": "synthetic",
        "currency": "USD",
        "account_type": "cash",
        "cash": "160",
        "settled_cash": "160",
        "unsettled_cash": "0",
        "buying_power": "160",
        "cash_basis": "before_reservations",
    }
    opening = PortfolioState(
        source="SYNTHETIC_RISK_FIXTURE_V09",
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
    state = PortfolioState.model_validate(
        opening.model_dump() | {
            "as_of": NOW,
            "history_start": opening.as_of,
            "daily_pnl": "0",
            "experimental_pnl": "0",
            "daily_pnl_start": NOW.replace(hour=0),
            "daily_pnl_as_of": NOW,
            "experimental_attribution": ExperimentalAttribution(
                baseline_id="synthetic-baseline",
                source="SYNTHETIC_OWNER_CLASSIFICATION",
                as_of=NOW,
                complete=True,
                account_ids=("synthetic",),
                positions=(),
                open_orders=(),
            ),
        }
    )
    # Fixture-only thresholds exercise code paths. They are not current policy decisions.
    policy = InvestmentPolicy(
        max_daily_loss="10",
        max_experimental_loss="20",
        max_state_age_seconds=120,
        daily_loss_timezone="UTC",
    )
    trade = HypotheticalTrade(
        account_id="synthetic",
        symbol="AAPL",
        side="buy",
        quantity="1",
        limit_price="100",
        estimated_fees="0",
        asset_type="equity",
        leverage_factor="1",
        thesis="Synthetic test thesis",
        entry_thesis="Synthetic test entry",
        exit_invalidation_thesis="Synthetic test exit condition",
    )
    base = DiagnosticInput(
        environment="research",
        policy=policy,
        opening=opening,
        state=state,
        trade=trade,
        kill_switch=KillSwitch(enabled=False, as_of=NOW),
        evaluated_at=NOW,
        market_data_at=NOW,
        core_session_open=True,
        proposal_id="proposal-1",
        technical_eligibility="ELIGIBLE",
    )

    def changed(**kwargs):
        return DiagnosticInput.model_validate(base.model_dump() | kwargs)

    def revised_trade(**kwargs):
        return HypotheticalTrade.model_validate(trade.model_dump() | kwargs)

    order = StateOrder(
        account_id="synthetic", order_id="pending-1", symbol="MSFT", side="buy",
        quantity="1", filled_quantity="0", limit_price="80", remaining_fees="0",
        status="open", asset_type="equity", leverage_factor="1", order_type="limit",
        time_in_force="day", session="core", complex=False,
    )
    pending_state = state.model_copy(update={
        "open_orders": (order,),
        "experimental_attribution": state.experimental_attribution.model_copy(update={
            "open_orders": (ExperimentalOrder(account_id="synthetic", order_id="pending-1"),),
        }),
    })
    outside_position = StatePosition(
        account_id="synthetic", symbol="TSLA", quantity="1", price="100",
        cost_basis="100", price_as_of=NOW, asset_type="equity", leverage_factor="1",
        market_value="100", observed_at=NOW,
    )
    holding_account = dict(account, cash="60", settled_cash="60", buying_power="60")
    holding_opening = PortfolioState.model_validate(opening.model_dump() | {
        "accounts": (holding_account,),
        "positions": (StatePosition.model_validate(outside_position.model_dump() | {
            "price_as_of": opening.as_of, "observed_at": opening.as_of,
        }),),
    })
    holding_state = PortfolioState.model_validate(state.model_dump() | {
        "accounts": (holding_account,), "positions": (outside_position,),
        "experimental_attribution": ExperimentalAttribution(
            baseline_id="synthetic-baseline", source="SYNTHETIC_OWNER_CLASSIFICATION",
            as_of=NOW, complete=True, account_ids=("synthetic",),
            positions=(ExperimentalPosition(
                account_id="synthetic", symbol="TSLA", quantity="1", cost_basis="100"
            ),), open_orders=(),
        ),
    })
    return {
        "baseline_review": base,
        "cap_160": changed(trade=revised_trade(limit_price="161")),
        "proposed_1000_isolated": changed(proposed_capital_scenario="1000", trade=revised_trade(limit_price="500")),
        "insufficient_cash": changed(trade=revised_trade(limit_price="170")),
        "whole_share_unaffordable": changed(trade=revised_trade(limit_price="170", quantity="1")),
        "pending_reservation": changed(state=pending_state),
        "reservation_released": base,
        "concentration_increase": base,
        "existing_nonallowlisted_holding": changed(
            opening=holding_opening, state=holding_state,
            trade=revised_trade(symbol="MSFT", limit_price="50"),
        ),
        "position_exposure_limit": changed(policy=InvestmentPolicy.model_validate(
            policy.model_dump() | {"max_position_exposure": "90"}
        )),
        "concentration_limit": changed(policy=InvestmentPolicy.model_validate(
            policy.model_dump() | {"max_concentration": "0.50"}
        )),
        "overlapping_positions": changed(
            opening=holding_opening, state=holding_state,
            trade=revised_trade(symbol="TSLA", limit_price="50"),
        ),
        "missing_policy": changed(policy=None),
        "missing_price": changed(market_data_at=None),
        "stale_quote": changed(market_data_at=NOW - timedelta(minutes=3)),
        "unsupported_security": changed(trade=revised_trade(symbol="TSLA")),
        "unsupported_order": changed(trade=revised_trade(order_type="market")),
        "kill_switch": changed(kill_switch=KillSwitch(enabled=True, as_of=NOW)),
        "daily_loss_unset": changed(policy=InvestmentPolicy()),
        "wrong_environment": changed(environment="production"),
        "duplicate_proposal": changed(existing_proposal_ids=("proposal-1",)),
        "session_closed": changed(core_session_open=False),
        "technically_ineligible": changed(technical_eligibility="INELIGIBLE"),
        "multiple_violations": changed(
            existing_proposal_ids=("proposal-1",), core_session_open=False,
            kill_switch=KillSwitch(enabled=True, as_of=NOW),
            trade=revised_trade(symbol="TSLA", limit_price="170"),
        ),
    }
