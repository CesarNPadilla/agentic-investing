"""Write deterministic synthetic v0.9 diagnostic evidence; no network or broker access."""

import json
from pathlib import Path

from risk.diagnostic_fixtures_v09 import scenarios
from risk.diagnostic_harness import diagnose
from risk.evaluator import digest
from risk.policy import InvestmentPolicy

OUT = Path("docs/examples/risk-diagnostics-v09")


def write(name, value):
    (OUT / name).write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    inputs = scenarios()
    outputs = {name: diagnose(item).model_dump(mode="json") for name, item in inputs.items()}
    write("policy-snapshots.json", {
        "current_authorized": InvestmentPolicy().model_dump(mode="json"),
        "fixture_only": inputs["baseline_review"].policy.model_dump(mode="json"),
        "proposed_capital": {"amount": "1000", "status": "PROPOSAL_REQUIRES_HUMAN_APPROVAL"},
    })
    write("scenarios.json", {
        "classification": "SYNTHETIC_DIAGNOSTIC_ONLY",
        "scenarios": {name: item.model_dump(mode="json") for name, item in inputs.items()},
    })
    write("evaluations.json", {"classification": "SYNTHETIC_DIAGNOSTIC_ONLY", "results": outputs})
    write("risk-control-inventory.json", {
        "version": "v09",
        "source": "docs/risk-engine-readiness-v09.md",
        "controls": {
            "maximum_position_size": "POLICY_UNDEFINED",
            "single_security_concentration": "PARTIAL",
            "maximum_portfolio_exposure": "PARTIAL",
            "available_cash": "IMPLEMENTED_AND_TESTED",
            "experimental_capital_limit": "IMPLEMENTED_AND_TESTED",
            "allowed_securities": "IMPLEMENTED_AND_TESTED",
            "allowed_order_types": "IMPLEMENTED_AND_TESTED",
            "trading_session": "PARTIAL",
            "daily_loss": "POLICY_UNDEFINED",
            "duplicate_conflicting_orders": "PARTIAL",
            "positions_and_pending_orders": "IMPLEMENTED_AND_TESTED",
            "kill_switch": "IMPLEMENTED_AND_TESTED",
            "market_data_freshness": "PARTIAL",
            "missing_policy": "IMPLEMENTED_AND_TESTED",
            "environment_isolation": "PARTIAL",
        },
    })
    write("replay-verification.json", {
        "exact_replay": all(diagnose(item).model_dump(mode="json") == outputs[name]
                            for name, item in inputs.items()),
        "scenario_digest": digest({name: item for name, item in inputs.items()}),
        "result_digest": digest(outputs),
        "scenario_count": len(inputs),
        "limitations": [
            "No broker methods or real portfolio state exercised",
            "Fixture-only daily loss and freshness thresholds are not authorized policy",
            "No historical Risk Engine outcomes inferred from v0.8 experiments",
            "No 2026 out-of-sample data accessed",
        ],
    })


if __name__ == "__main__":
    main()
