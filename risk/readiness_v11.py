"""Nonexecuting readiness audit: synthetic qualification never releases a gate."""
import hashlib
import json
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

REQUIRED = (
    "runtime_integration", "whole_account_loss", "portfolio_exposure", "trusted_sources_clock",
    "roles_reset", "funding_attribution", "environment_qualification", "authenticated_approval",
    "historical_qualification", "corporate_actions", "strategy_eligibility", "paper_start_authorization",
    "forward_paper_60", "broker_security", "backup_recovery_monitoring", "audit_integrity",
    "live_authorization",
)


class ReadinessItem(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    requirement_id: str
    status: Literal["BLOCKED", "MISSING", "SYNTHETIC_ONLY"]
    explanation: str = Field(min_length=1)


class ReadinessReport(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    schema_version: Literal["v11-readiness-audit-v1"] = "v11-readiness-audit-v1"
    items: tuple[ReadinessItem, ...]
    configured_research_cap_usd: str
    funding_confirmed: Literal[False] = False
    v11_complete: Literal[False] = False
    paper_start_ready: Literal[False] = False
    live_ready: Literal[False] = False
    execution_available: Literal[False] = False
    forward_paper_sessions: Literal[0] = 0
    source_references: tuple[dict[str, str], ...]

    @model_validator(mode="after")
    def complete_inventory(self):
        ids = [item.requirement_id for item in self.items]
        if len(ids) != len(set(ids)) or set(ids) != set(REQUIRED):
            raise ValueError("Every required readiness gate must occur exactly once")
        return self


def build_current_readiness(root: Path):
    """Audit the current frozen package; never accepts a claimed production pass.

    Only current snapshot sources are checked. Prior manifests retain historical
    source digests and are not recursively compared with subsequently edited code.
    Future verified qualification requires a separate reviewed schema/workflow.
    """
    root = root.resolve()
    files = ["docs/examples/risk-policy-v11g/implementation-status.json",
             "docs/examples/risk-policy-v103/production-risk-decisions.json",
             "docs/examples/risk-policy-v103/operational-decisions.json",
             "docs/examples/capital-cap-change-v03.json", "conf/investment-policy-v03.json"]
    references, documents = [], {}
    for path in files:
        raw = (root/path).read_bytes()
        references.append({"path": path, "sha256": hashlib.sha256(raw).hexdigest()})
        documents[path] = json.loads(raw)
    current = documents[files[0]]
    if current.get("phase") != "v1.1g" or current.get("execution_available") is not False:
        raise ValueError("Unrecognized current implementation snapshot")
    for ref in current["source_references"]:
        target = (root/ref["path"]).resolve()
        if not target.is_relative_to(root) or hashlib.sha256(target.read_bytes()).hexdigest() != ref["sha256"]:
            raise ValueError("Current source digest mismatch")
    capital = documents[files[3]]
    if (capital.get("funding_confirmed") is not False
            or current.get("funding_confirmed") is not False
            or current.get("forward_paper_sessions") != 0
            or current.get("paper_execution_approved") is not False
            or current.get("live_execution_approved") is not False):
        raise ValueError("Changed funding/authorization evidence requires fresh reviewed package")
    policy = documents[files[-1]]
    if policy["production_trading"] is not False or policy["automated_trading"] is not False:
        raise ValueError("Disabled execution invariant violated")
    if documents[files[1]]["whole_account_daily_loss_threshold"] is not None:
        raise ValueError("New whole-account value requires fresh reviewed readiness package")
    descriptions = {
        "runtime_integration": "Synthetic libraries are not wired to the runtime API/broker boundary.",
        "whole_account_loss": "Whole-account threshold, measurement/day/reset choices remain unspecified.",
        "portfolio_exposure": "Whole-portfolio limits/denominators and concentration/correlation rules remain unspecified.",
        "trusted_sources_clock": "Webull quote/account APIs and NYSE calendar selected; entitlement, source coherence, calendar integration and clock qualification pending.",
        "roles_reset": "Human operational roles and authenticated correction/reset workflow are missing.",
        "funding_attribution": "Owner plans USD 1,000 funding; actual deposit and sleeve attribution unconfirmed.",
        "environment_qualification": "No qualified named paper/live environment release.",
        "authenticated_approval": "Synthetic digest binding is not authenticated human approval.",
        "historical_qualification": "Historical qualification remains blocked; 2026 OOS stays sealed.",
        "corporate_actions": "Corporate-action vintage/accounting qualification remains blocked.",
        "strategy_eligibility": "Neither strategy has qualifying eligibility evidence.",
        "paper_start_authorization": "Starting forward paper needs separate explicit authorization.",
        "forward_paper_60": "Forward paper remains 0/60 qualifying sessions.",
        "broker_security": "Live broker least-privilege/security/reconciliation qualification is incomplete.",
        "backup_recovery_monitoring": "Disposable process recovery passes; backup/restore and production operations remain unqualified.",
        "audit_integrity": "No externally anchored immutable production audit qualification.",
        "live_authorization": "No separate explicit live release permission.",
    }
    owner_path = root/"docs/examples/remaining-owner-inputs-v11/input-register-v5.json"
    newer_owner = root/"docs/examples/remaining-owner-inputs-v11/input-register-v6.json"
    if newer_owner.exists():
        owner_path = newer_owner
    latest_owner = root/"docs/examples/remaining-owner-inputs-v11/input-register-v7.json"
    if latest_owner.exists():
        owner_path = latest_owner
    selected_owner = root/"docs/examples/remaining-owner-inputs-v11/input-register-v8.json"
    if selected_owner.exists():
        owner_path = selected_owner
    if owner_path.exists():
        owner_raw = owner_path.read_bytes()
        owner = json.loads(owner_raw)
        selected = {row["stable_id"]: row["concrete_response"] for row in owner["items"]}
        expected = {"PROD-ACCOUNT-DAILY-LOSS": ("0.01", "start_of_day"),
                    "PROD-GROSS-EXPOSURE": ("1.00", "current_snapshot"),
                    "PROD-SECURITY-CONCENTRATION": ("0.10", "current_snapshot")}
        for key, (fraction, timing) in expected.items():
            response = selected[key]
            if (response["fraction"] != fraction or response["denominator_evaluation_time"] != timing
                    or response["denominator"] != "total account equity" or response["active"] is not False):
                raise ValueError("Unrecognized owner limits require fresh reviewed package")
        for ref in owner["source_references"]:
            target = (root/ref["path"]).resolve()
            if not target.is_relative_to(root) or hashlib.sha256(target.read_bytes()).hexdigest() != ref["sha256"]:
                raise ValueError("Owner input source digest mismatch")
        references.append({"path": owner_path.relative_to(root).as_posix(),
                           "sha256": hashlib.sha256(owner_raw).hexdigest()})
        descriptions["whole_account_loss"] = "Recorded 1% of start-of-day total account equity; day/reset/trusted methodology and runtime enforcement remain incomplete."
        descriptions["portfolio_exposure"] = "Recorded gross 100% and per-security 10% of current total account equity; sector/correlation and existing-breach rules and runtime integration remain incomplete."
    items = tuple(ReadinessItem(requirement_id=key,
        status="SYNTHETIC_ONLY" if key in {"runtime_integration", "authenticated_approval", "backup_recovery_monitoring"} else "BLOCKED",
        explanation=descriptions[key]) for key in REQUIRED)
    return ReadinessReport(items=items, configured_research_cap_usd=policy["agent_experimental_capital_limit"],
                           source_references=tuple(references))
