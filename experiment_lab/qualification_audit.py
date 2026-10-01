"""Record a fail-closed qualification decision without opening reserved OOS data."""

import hashlib
import json
from datetime import UTC, date, datetime
from pathlib import Path


def audit(raw_snapshot: Path, prior_plan: Path, prior_results: Path, output: Path) -> dict:
    if output.exists():
        raise ValueError("Qualification audit is immutable")
    raw = raw_snapshot.read_bytes()
    snapshot = json.loads(raw)
    if snapshot.get("scope") != "DEVELOPMENT_AND_VALIDATION_ONLY":
        raise ValueError("Snapshot scope is not isolated")
    if snapshot.get("adjustment_mode") != "raw" or snapshot.get("holdout_exposed") is not False:
        raise ValueError("Snapshot provenance is not isolated")
    if any(date.fromisoformat(bar["timestamp"][:10]) > date(2025, 12, 31)
           for bar in snapshot["bars"]):
        raise ValueError("Reserved OOS bar in candidate snapshot")
    plan = json.loads(prior_plan.read_text(encoding="utf-8"))
    if (prior_results / "out-of-sample.json").exists():
        raise ValueError("Unexpected OOS results file")
    report = {
        "recorded_at": datetime.now(UTC).isoformat(),
        "scope": "DEVELOPMENT_AND_VALIDATION_ONLY",
        "raw_snapshot_sha256": hashlib.sha256(raw).hexdigest(),
        "raw_bar_count": len(snapshot["bars"]),
        "raw_latest_session_date": max(bar["timestamp"][:10] for bar in snapshot["bars"]),
        "existing_plan_id": plan["plan_id"],
        "existing_gates": plan["gates"],
        "next_qualifying_validation_gates_frozen_before_run": {
            "minimum_observations": 126,
            "minimum_trades": 5,
            "maximum_drawdown": "0.25",
            "maximum_turnover": "3",
            "acceptable_data_quality": [],
            "zero_lookahead_violations": True,
            "zero_policy_bypasses": True,
            "reproducibility": True,
            "holdout_integrity": True,
        },
        "next_qualifying_validation_gate_status": "NOT_RUN_PROVIDER_QUALIFICATION_FAILED",
        "new_qualifying_validation_executed": False,
        "new_validation_blocker": "FMP_HTTP_402_AND_UNPROVEN_FUNDAMENTAL_REVISIONS_AND_ACTION_VINTAGE",
        "reserved_oos_opened": False,
        "reserved_oos_results_calculated": False,
        "paper_eligibility": "NOT_ELIGIBLE",
        "forward_paper_sessions": 0,
        "paper_execution": "DISABLED",
        "production_execution": "DISABLED",
    }
    output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    return report
