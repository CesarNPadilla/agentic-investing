# Phase v1.0.3 — blanket approval reconciliation

All **35 register decisions** now record `APPROVE_AS_PROPOSED`; the 25 newly approved entries link to the [direct user instruction](examples/risk-policy-v103/human-instruction-provenance.json). N01–N10 retain their original provenance and exact numerical definitions. All operational matrix responses also record approval as proposed. Earlier packages remain unchanged historical snapshots. No identity or timestamp was invented.

See the current [decision register](examples/risk-policy-v103/decision-register.json). Approval applies to the existing text; an approved request to choose a limit/source/owner does not supply that missing selection. Approval status and operational readiness are separate. Existing blocking dependencies are preserved conservatively pending evidence/selection reconciliation.

| Area | Recorded approval | Remaining requirement |
| --- | --- | --- |
| CAP-A | Future $1,000 policy ceiling approved | Versioned policy change, impact review, tests and separate deployment/activation; executable cap stays $160 |
| CAP-B | Reviewed funded-sleeve baseline proposal approved | Actual deposit evidence and attribution inventory; funding_confirmed remains false |
| CAP-C | Separate environment-specific authorization proposal approved | Named qualified environment and explicit permission to use it; execution_authorized remains false |
| Whole-account loss | Existing request/method proposal approved | Dollar threshold, any percentage denominator, timezone/baseline, check frequency and reset selections; threshold remains null / fail closed |
| Portfolio exposure | Existing design requests approved | Gross and per-security limits/denominators, sector/correlation method and thresholds, breach/new-buy treatment |
| Trusted data and roles | Source/ownership qualification proposals approved | Named quote/snapshot/calendar sources, clock monitoring and authenticated human role assignments |
| Outage/recovery | Proposed fail-closed behavior approved | Persistent outage/restart latch scope where proposal is null/unresolved; qualified recovery evidence |
| Exceptions | Existing restrictive proposal text approved | No executable exception path authorized; any future mechanism requires explicit scope and authority within nonwaivable safety controls |
| AUTH-V11 | Implementation-only proposal approved subject to dependencies | Dependent concrete policy decisions/evidence remain incomplete; authorization is not effective for blocked workstreams; v1.1 remains unstarted |

Approval of AUTH-V11 is recorded; it is no longer awaiting an approval response. Its prerequisite clause still applies. No paper/live permission, operational activation or actual capital movement is inferred. Missing requirements continue to fail closed.

This update changes documentation only. Current executable cap remains **$160**; all numerical limits remain inactive; whole-account daily-loss amount remains **UNSET / FAIL CLOSED**. Risk engine, broker, strategies, historical/OOS evidence and execution flags are unchanged. 2026 OOS remains sealed; forward paper 0/60; paper/production execution disabled. v1.1 has not started.

Validation: eight new JSON files parse, all source and provenance digests match, register and detail responses reconcile, N01–N10 numerical definitions are unchanged, approver/timestamp fields remain null, historical snapshots and executable files are unchanged, and git diff --check passes.
