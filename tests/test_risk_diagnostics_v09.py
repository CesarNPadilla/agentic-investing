from risk.diagnostic_fixtures_v09 import scenarios
from risk.diagnostic_harness import diagnose
from risk.evaluator import digest
from risk.policy import InvestmentPolicy


def test_all_synthetic_scenarios_replay_exactly():
    for name, item in scenarios().items():
        result = diagnose(item)
        assert result == diagnose(item), name
        assert result.audit_id == digest(("risk-diagnostic-v09", result.input_snapshot_digest))
        assert result.policy_digest == (digest(item.policy) if item.policy else None)
        assert result.execution_available is False


def test_policy_cap_and_proposed_capital_remain_separate():
    cases = scenarios()
    assert cases["baseline_review"].policy.agent_experimental_capital_limit == 160
    assert diagnose(cases["baseline_review"]).decision == "REVIEW_REQUIRED"
    assert "experimental_capital" in diagnose(cases["cap_160"]).reason_codes
    proposed = diagnose(cases["proposed_1000_isolated"])
    assert proposed.proposed_capital_scenario == 1000
    assert proposed.proposed_capital_is_authorized is False
    assert "experimental_capital" in proposed.reason_codes
    assert InvestmentPolicy().agent_experimental_capital_limit == 160


def test_reservations_and_release_are_explicit():
    cases = scenarios()
    pending = diagnose(cases["pending_reservation"])
    released = diagnose(cases["reservation_released"])
    assert pending.cash_after_reservations_and_proposal == -20
    assert "settled_cash" in pending.reason_codes
    assert released.cash_after_reservations_and_proposal == 60
    assert released.decision == "REVIEW_REQUIRED"


def test_independent_failures_and_missing_evidence():
    cases = scenarios()
    assert {"duplicate_proposal", "kill_switch", "session_closed", "proposed_order"} <= set(
        diagnose(cases["multiple_violations"]).reason_codes
    )
    assert "missing_policy" in diagnose(cases["missing_policy"]).missing_evidence
    assert "missing_market_price" in diagnose(cases["missing_price"]).missing_evidence
    assert "stale_market_price" in diagnose(cases["stale_quote"]).failed_controls
    assert "configured_max_daily_loss" in diagnose(cases["daily_loss_unset"]).reason_codes
    assert "diagnostic_environment" in diagnose(cases["wrong_environment"]).reason_codes
    assert "technically_ineligible" in diagnose(cases["technically_ineligible"]).reason_codes


def test_position_and_concentration_limits_are_fixture_only():
    cases = scenarios()
    assert "position_limit" in diagnose(cases["position_exposure_limit"]).reason_codes
    assert "concentration_limit" in diagnose(cases["concentration_limit"]).reason_codes
    existing = diagnose(cases["existing_nonallowlisted_holding"])
    assert existing.pre_proposal_exposure == 100
    assert existing.post_proposal_exposure == 150
    assert existing.decision == "REVIEW_REQUIRED"
    assert "proposed_order" in diagnose(cases["overlapping_positions"]).reason_codes
