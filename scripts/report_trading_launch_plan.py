"""Offline planning report and visual; never admission or trading authorization."""

import hashlib
import json
from datetime import date, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
NYSE = "https://www.nyse.com/trade/hours-calendars"
HOLIDAYS = [
    "2026-11-26",
    "2026-12-25",
    "2027-01-01",
    "2027-01-18",
    "2027-02-15",
    "2027-03-26",
    "2027-05-31",
    "2027-06-18",
    "2027-07-05",
    "2027-09-06",
    "2027-11-25",
    "2027-12-24",
]


def session_end(start, count=60):
    if not date(2026, 10, 12) <= start <= date(2027, 8, 1):
        raise ValueError("Planning calendar coverage is October 2026 through 2027")
    holidays = {date.fromisoformat(value) for value in HOLIDAYS}
    day, sessions = start, 0
    while sessions < count:
        if day.weekday() < 5 and day not in holidays:
            sessions += 1
        if sessions < count:
            day += timedelta(days=1)
    return day


def main():
    gates_path = ROOT / "docs/examples/webull-sandbox/current-launch-gates.json"
    gates = json.loads(gates_path.read_bytes())
    if any(
        gates.get(flag) is not False
        for flag in ("execution_available", "trial_started", "live_authorized")
    ):
        raise ValueError(
            "October 12 pre-launch snapshot no longer matches current gates; prepare a new dated plan"
        )
    report = {
        "schema_version": "trading-launch-plan-v1",
        "as_of_client_date": "2026-10-12",
        "current_phase": "PHASE_3_PRE_PAPER_RELEASE_QUALIFICATION",
        "next_work_package": "WEBULL_SOURCE_AND_RUNTIME_RELEASE_QUALIFICATION",
        "planning_only": True,
        "observed_disposable_controls_ceremony_percent": gates[
            "actual_disposable_controls_ceremony_percent"
        ],
        "observed_trial_launch_percent": gates["trial_launch_percent"],
        "observed_live_authorized": gates["live_authorized"],
        "overall_readiness_percent": None,
        "strategy_qualification": "RESEARCH_STRATEGIES_NOT_ELIGIBLE_NO_QUALIFYING_FORWARD_EVIDENCE",
        "provider": "WEBULL_RETAIL_CASH_SANDBOX",
        "paper_scope": "SCHB_ETF_CONTROL_PLUMBING_ONLY_INTC_DISABLED",
        "paper_start_target_window": ["2026-11-02", "2026-11-23"],
        "paper_first_month_review_window": ["2026-12-02", "2026-12-23"],
        "forecast_confidence": "LOW_CONDITIONAL_ENGINEERING_ESTIMATE_NOT_COMMITMENT",
        "forecast_assumptions": [
            "Useful Webull retail technical answers arrive October 19–26; provider timing is unknown.",
            "Remaining controls, source integration and Webull runner/release checks take approximately 2–4 weeks, partly in parallel; this is an effort estimate, not an accepted schedule.",
            "Account baseline, trusted sources, clock/isolation/recovery and acceptance tests pass without a material redesign.",
            "Required scoped owner paper activation is recorded after evidence review; sandbox mode alone is insufficient.",
            "A month of controls plumbing does not establish investment-strategy profitability or satisfy the separate 60-session strategy requirement.",
        ],
        "live_scenario": {
            "planning_window": "APRIL_TO_MAY_2027_IF_QUALIFIED_STRATEGY_PAPER_STARTS_IN_JANUARY",
            "confidence": "VERY_LOW_NO_COMMITTABLE_LIVE_DATE",
            "assumptions": [
                "A real frozen strategy clears historical/evidence eligibility and is approved for qualifying paper before January 2027.",
                "All 60 forward sessions qualify with no evidence gaps; acceptance criteria pass.",
                "Allow another 2–4 weeks for results review, production broker/data/control qualification and explicit human live release.",
                "Production funding/account and environment are independently verified; live-grade status coverage includes the deferred Nasdaq requirement unless separately amended.",
            ],
            "examples": [
                {
                    "qualified_strategy_paper_start": start,
                    "sixtieth_nyse_session": session_end(date.fromisoformat(start)).isoformat(),
                }
                for start in ["2027-01-04", "2027-01-19"]
            ],
            "guaranteed_start_date": None,
        },
        "calendar": {
            "source": NYSE,
            "holidays": HOLIDAYS,
            "early_close_days": ["2026-11-27", "2026-12-24", "2027-11-26"],
            "early_close_counts_as_session_only_if_qualified": True,
            "extraordinary_closures_and_evidence_gaps_extend_estimate": True,
        },
        "pending_paper": [
            "Webull quote-time/entitlement, authoritative halt bootstrap/coverage, coherent cash/activity/equity boundary and event/reconnect contracts.",
            "Current-key selection/revocation, protected recovery history and atomic reset admission, followed by actual-account review.",
            "Port/freeze the existing Alpaca-only SCHB plumbing configuration and runner for Webull sandbox; do not relabel the legacy config.",
            "Integrate idempotent orders, reservations, fills, cash/settlement, every-order/fill checks and bounded monitoring; persistent month runner and end-of-month handling.",
            "Deploy and verify least-privilege broker isolation, current one-second clock bound, restart/outage/kill-switch drills; resolve deferred remote-client qualification.",
            "Evidence audit, verified current cash-account baseline and required scoped owner activation.",
        ],
        "execution_available": False,
        "trial_started": False,
        "live_authorized": False,
        "source_digests": {
            str(gates_path.relative_to(ROOT)).replace("\\", "/"): hashlib.sha256(
                gates_path.read_bytes()
            ).hexdigest(),
            "conf/paper-etf-plumbing.json": hashlib.sha256(
                (ROOT / "conf/paper-etf-plumbing.json").read_bytes()
            ).hexdigest(),
            "docs/alpaca-paper-month.md": hashlib.sha256(
                (ROOT / "docs/alpaca-paper-month.md").read_bytes()
            ).hexdigest(),
        },
    }
    target = ROOT / "docs/examples/trading-launch-plan/plan-2026-10-12.json"
    target.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    template = (ROOT / "docs/visuals/trading-launch-plan.template.html").read_text(encoding="utf-8")
    html = template.replace(
        "__PLAN_JSON__", json.dumps(report, ensure_ascii=False).replace("</", "<\\/")
    )
    (ROOT / "docs/visuals/trading-launch-plan.html").write_text(html, encoding="utf-8")
    files = [
        "scripts/report_trading_launch_plan.py",
        "docs/trading-launch-plan.md",
        "docs/webull-release-work-package.md",
        "docs/visuals/trading-launch-plan.template.html",
        "docs/visuals/trading-launch-plan.html",
        "docs/examples/trading-launch-plan/plan-2026-10-12.json",
    ]
    evidence = {
        "schema_version": "trading-launch-plan-preparation-v1",
        "provenance": "User requested phase continuation, paper/live blockers and a visual flow with date estimates. Conditional forecasts are not approved launch dates.",
        "current_phase": report["current_phase"],
        "next_work_package": report["next_work_package"],
        "planning_artifacts_prepared": True,
        "interactive_calculations_checked": [
            "Both January/60-session scenarios",
            "Calendar-month boundaries",
            "Month-end clamp",
            "Non-session rollover",
            "Reject dates outside calendar coverage",
        ],
        "calendar_source": NYSE,
        "calendar_review_client_date": "2026-10-12",
        "forecast_confidence": report["forecast_confidence"],
        "trial_launch_percent": 0,
        "overall_readiness_percent": None,
        "execution_available": False,
        "trial_started": False,
        "live_authorized": False,
        "policy_strategy_and_historical_data_modified": False,
        "source_digests": {p: hashlib.sha256((ROOT / p).read_bytes()).hexdigest() for p in files},
    }
    (ROOT / "docs/examples/trading-launch-plan/preparation-2026-10-12.json").write_text(
        json.dumps(evidence, indent=2) + "\n", encoding="utf-8"
    )
    for directory in (ROOT / "conf", ROOT / "docs/examples"):
        for path in directory.rglob("*.json"):
            json.loads(path.read_bytes().decode("utf-8-sig"))
    for path, pin in report["source_digests"].items():
        if hashlib.sha256((ROOT / path).read_bytes()).hexdigest() != pin:
            raise ValueError("Planning input source changed during generation")
    print(
        "Planning report and interactive flow generated. No runtime, source, policy or execution gate changed."
    )


if __name__ == "__main__":
    main()
