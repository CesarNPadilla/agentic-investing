from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest
from pydantic import ValidationError

from risk.paper_daily_loss import BoundaryEvidence, evaluate_daily_loss, retain_boundary_evidence
from risk.paper_state import PaperState, PaperStateError
from tests.test_paper_control_pipeline import reader


def setup(tmp_path):
    account = reader().observe().model_copy(update={"equity": 990})
    store = PaperState.initialize(
        tmp_path / "paper.sqlite", account_binding=account.account_binding_sha256
    )
    evidence = BoundaryEvidence(
        account_binding=account.account_binding_sha256,
        source_digest="a" * 64,
        source_description="TEST FIXTURE",
        as_of=datetime(2026, 10, 5, 4, tzinfo=UTC),
        equity=1000,
    )
    return store, account, evidence


def test_fixed_denominator_threshold_and_sticky_restart(tmp_path):
    store, account, evidence = setup(tmp_path)
    retain_boundary_evidence(store, evidence)
    now = account.received_at
    result = evaluate_daily_loss(store, account, now=now, external_flow_total=0)
    assert result["daily_loss_limit"] == "10.00" and result["daily_loss_breach"]
    assert "DAILY_BOUNDARY_SOURCE_UNQUALIFIED" in result["blockers"]
    restarted = PaperState(store.path)
    recovered = account.model_copy(update={"equity": 1000})
    assert not evaluate_daily_loss(restarted, recovered, now=now, external_flow_total=0)[
        "daily_loss_breach"
    ]
    assert "ACCOUNT_DAILY_LOSS" in restarted.read()["latch_reasons"]


def test_missing_baseline_flows_and_stale_observation_block(tmp_path):
    store, account, evidence = setup(tmp_path)
    assert evaluate_daily_loss(store, account, now=account.received_at)["daily_net_pnl"] is None
    retain_boundary_evidence(store, evidence)
    assert evaluate_daily_loss(store, account, now=account.received_at)["daily_net_pnl"] is None
    assert (
        evaluate_daily_loss(
            store, account, now=account.received_at + timedelta(seconds=61), external_flow_total=0
        )["daily_net_pnl"]
        is None
    )


def test_baseline_cannot_be_replaced_or_invented_from_intraday_timestamp(tmp_path):
    store, _, evidence = setup(tmp_path)
    retain_boundary_evidence(store, evidence)
    with pytest.raises(PaperStateError):
        retain_boundary_evidence(store, evidence.model_copy(update={"equity": Decimal(2000)}))
    with pytest.raises(ValidationError):
        BoundaryEvidence.model_validate(
            dict(evidence.model_dump(), as_of=datetime(2026, 10, 5, 15, tzinfo=UTC))
        )


def test_previous_day_record_cannot_be_used_under_current_day_key(tmp_path):
    store, account, evidence = setup(tmp_path)
    previous = evidence.model_copy(update={"as_of": evidence.as_of - timedelta(days=1)})
    with store.transaction() as state:
        state["paper_day_boundary_evidence"] = {"2026-10-05": previous.model_dump(mode="json")}
    with pytest.raises(PaperStateError):
        evaluate_daily_loss(store, account, now=account.received_at, external_flow_total=0)


def test_blocked_account_does_not_produce_pnl_or_safe_claim(tmp_path):
    store, account, evidence = setup(tmp_path)
    retain_boundary_evidence(store, evidence)
    blocked = account.model_copy(update={"account_unblocked": False})
    result = evaluate_daily_loss(store, blocked, now=account.received_at, external_flow_total=0)
    assert result["daily_net_pnl"] is None and not result["daily_pnl_evaluated"]
    assert "DAILY_LOSS_SNAPSHOT_UNQUALIFIED" in result["blockers"]
