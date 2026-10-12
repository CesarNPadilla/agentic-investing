"""Integrated read-only paper observer. Not a qualified trading/month-trial runner."""

import json
import subprocess
from datetime import UTC, datetime, timedelta
from decimal import Decimal

from integrations.brokers.alpaca_paper_activities import AlpacaPaperActivityReader
from integrations.brokers.alpaca_paper_read import AlpacaPaperAccountReader
from market_data.alpaca_evidence import AlpacaPaperQuoteReader
from market_data.nyse_calendar import NysePublishedCalendar
from portfolio.paper_cash_reconciliation import reconcile_cash
from portfolio.paper_daily_flows import retain_daily_activity
from portfolio.paper_fill_ledger import PaperFillLedger
from risk.paper_clock import check_windows_time
from risk.paper_daily_loss import NY, evaluate_daily_loss
from risk.paper_settlement import simulated_settlement
from strategies.paper_etf_scope import selected_symbol


def observe_once(
    *,
    account_reader,
    activity_reader,
    quote_reader,
    calendar,
    ledger,
    clock_check,
    now,
    daily_activity_reader=None,
    symbol="INTC",
):
    # Every source cycle remains latched; no broker mutations exist in this worker.
    daily = None
    daily_activity = None
    stage = "ACCOUNT_READ"
    try:
        account = account_reader.observe()
        before = ledger.read()
        stage = "ACTIVITY_READ"
        batch = activity_reader.read(
            after=datetime.fromisoformat(before["acquisition_cutoff"]) - timedelta(days=1),
            until=now(),
        )
        ledger.import_batch(batch, account_binding=account.account_binding_sha256)
        if daily_activity_reader is not None:
            current = now()
            boundary = (
                ledger.store.read()
                .get("paper_day_boundary_evidence", {})
                .get(current.astimezone(NY).date().isoformat())
            )
            if boundary is not None:
                stage = "DAILY_ACTIVITY_READ"
                day_batch = daily_activity_reader.read(
                    after=datetime.fromisoformat(boundary["as_of"]), until=current
                )
                daily_activity = retain_daily_activity(
                    ledger.store, day_batch, account_binding=account.account_binding_sha256
                )
        stage = "ACCOUNT_RECHECK"
        account = account_reader.observe()
        instant = now()
        state = ledger.store.read()
        cash = reconcile_cash(ledger.read(), account, now=instant, ledger_binding=state["binding"])
        settlement = simulated_settlement(ledger.read(), calendar, now=instant)
        clock = clock_check()
        stage = "DAILY_LOSS_CHECK"
        daily = evaluate_daily_loss(ledger.store, account, now=instant)
        stage = "QUOTE_READ"
        quote = quote_reader.read(symbol)
        instant = now()
        reasons = set(cash["blockers"]) | set(settlement["blockers"]) | set(clock["blockers"])
        reasons |= set(daily["blockers"])
        if daily_activity:
            reasons |= set(daily_activity["blockers"])
        reasons |= set(quote.blockers(instant)) | set(calendar.schedule_reasons(instant))
        reasons.update(
            {
                "EXTERNAL_RESET_UNQUALIFIED",
                "STATUS_BOOTSTRAP_UNQUALIFIED",
                "ORDER_RUNNER_NOT_QUALIFIED",
            }
        )
        if account.open_orders_count:
            reasons.add("OPEN_ORDER_RESERVATIONS_REQUIRE_RECONCILIATION")
        # Dedicated account: cumulative P&L is valid only if unexplained flows/cash remain blocked.
        if account.equity - Decimal(1000) <= Decimal(-100):
            reasons.add("CUMULATIVE_LOSS_STOP")
        if account.positions_market_value > account.equity or account.equity <= 0:
            reasons.add("ACCOUNT_GROSS_OR_EQUITY_STOP")
        if any(
            abs(p.market_value) > account.equity * Decimal("0.10")
            for p in account.position_quantities
        ):
            reasons.add("ACCOUNT_SECURITY_CONCENTRATION")
        ledger.store.record_observation(account, sorted(reasons))
        return {
            "account_observed": True,
            "ledger_imported": True,
            "quote_observed": True,
            "active_scope": bool(account.positions_count or account.open_orders_count),
            "cash_matches": cash["cash_matches"],
            "positions_match": cash["positions_match"],
            "daily_loss": daily,
            "daily_activity": daily_activity,
            "blockers": sorted(reasons),
            "execution_available": False,
            "trial_started": False,
        }
    except (
        RuntimeError,
        ValueError,
        TypeError,
        OSError,
        ArithmeticError,
        subprocess.SubprocessError,
    ):
        try:
            ledger.store.latch("INTEGRATED_OBSERVER_FAILED")
            ledger.store.latch(stage + "_FAILED")
        except (RuntimeError, ValueError, TypeError, OSError):
            return {
                "blockers": ["OBSERVER_PERSISTENCE_FAILED"],
                "execution_available": False,
                "trial_started": False,
            }
        return {
            "blockers": ["INTEGRATED_OBSERVER_FAILED", stage + "_FAILED"],
            "daily_loss": daily,
            "daily_activity": daily_activity,
            "execution_available": False,
            "trial_started": False,
        }


def windows_clock(root):
    policy_path = root / "conf/paper-clock-policy.json"
    policy = json.loads(policy_path.read_text(encoding="utf-8")) if policy_path.exists() else {}
    result = subprocess.run(
        ["w32tm", "/query", "/status", "/verbose"],
        capture_output=True,
        text=True,
        timeout=10,
        check=False,
    )
    if result.returncode:
        return {"blockers": ["CLOCK_QUERY_FAILED"]}
    return check_windows_time(
        result.stdout,
        approved_source=policy.get("source"),
        max_error_seconds=policy.get("max_error_seconds"),
    )


def build_cycle(root, env_values, ledger_path):
    key, secret = env_values["AIL_ALPACA_API_KEY"], env_values["AIL_ALPACA_API_SECRET"]
    symbol = selected_symbol(root)
    return lambda: observe_once(
        account_reader=AlpacaPaperAccountReader(key, secret),
        activity_reader=AlpacaPaperActivityReader(key, secret),
        daily_activity_reader=AlpacaPaperActivityReader(key, secret),
        quote_reader=AlpacaPaperQuoteReader(key, secret),
        calendar=NysePublishedCalendar(root / "conf/nyse-calendar-2026.json"),
        ledger=PaperFillLedger(ledger_path),
        clock_check=lambda: windows_clock(root),
        now=lambda: datetime.now(UTC),
        symbol=symbol,
    )
