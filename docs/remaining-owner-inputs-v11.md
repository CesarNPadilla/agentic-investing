# Remaining owner inputs ? v1.1

The engineering foundation and readiness audit are complete through v1.1h. The next dependent step is to specify inputs that the approved proposals left blank. This is a request for concrete choices, not a request to repeat APPROVE_AS_PROPOSED. Existing decision responses stay unchanged. No new implementation phase is declared complete.

## First response: account-wide risk

Copy and fill the following. Values apply to the whole account, including existing non-sleeve holdings and pending buy commitments; they do not reuse sleeve values by implication.

- PROD-ACCOUNT-DAILY-LOSS - **1% of total account equity, owner-specified; supersedes the earlier $1 amount**. Inactive pending measurement, day/reset method and activation; denominator is now start-of-day equity.
- PROD-ACCOUNT-DAILY-METHOD ? realized + unrealized net fees and external-flow adjustment: ______; timezone/day boundary: ______; baseline: ______; check frequency: ______; breach/open-order review and authenticated reset procedure: ______
- PROD-GROSS-EXPOSURE - **100% of total account equity, owner-specified**. Inactive pending measurement and activation; denominator is now current equity.
- PROD-SECURITY-CONCENTRATION - **10% of total account equity per security, owner-specified**. Inactive pending treatment of existing breaches/increasing buys; denominator is now current equity.
- PROD-SECTOR-CORRELATION ? taxonomy/method/thresholds: ______; or explicitly defer with its affected gate blocked
- PROD-EXISTING-HOLDINGS ? reporting and new-buy restrictions on existing breaches: ______; no automatic liquidation

The owner specified the two percentages above; no other account-wide values were selected. The approved sleeve $20/2%, 25% and 75% remain separate scope-specific controls. Unresolved required details continue to fail closed.

## Subsequent response: operations and funding

- Trusted quote/snapshot/calendar source names, entitlement/provenance and qualification evidence; clock monitoring and failure criteria.
- Named policy owner, risk reviewer, implementation owner, deployment approver, live approver and kill-switch reset authority; explicit combined roles if applicable.
- Persistent outage/recovery rules, authenticated corrections/resets, and exact exception restrictions. No executable exception path exists.
- Actual funded-deposit and reviewed sleeve-attribution evidence when available; a named qualified environment and separate permission to use it. Planned funding does not confirm a deposit or authorize production orders. Do not include credentials.

The [current input register](examples/remaining-owner-inputs-v11/input-register-v8.json) records the daily-loss, gross-exposure and per-security percentages. The [per-security instruction](examples/remaining-owner-inputs-v11/security-concentration-limit.json) records the 10% limit. The [explicit instruction](examples/remaining-owner-inputs-v11/whole-account-percentage-limits.json) supersedes the earlier inferred $1 amount, whose record remains historical. No identity or timestamp was invented. Other concrete responses remain null. [Readiness review 011h](human-review-011h.md) remains historical overall readiness evidence; these new inputs do not clear its method, integration or activation gates.

Current local research cap is $1,000. Funding is unconfirmed; paper/live execution disabled; 2026 OOS sealed; forward paper 0/60. This document changes no policy, strategy, historical result, broker, runtime or execution flag.

Denominator timing was confirmed by assent to the proposed distinction: fixed start-of-day daily loss, current-equity gross/security limits. See [review 011i](human-review-011i.md). Timezone/day boundary is now America/New_York calendar midnight. Existing holdings above 10% remain reported, further buys in that security block and human review is required without liquidation. Reset/check-frequency and operational ownership remain unspecified.

Reset/monitoring update: one named human account owner authenticated outside agent runtime; next NY trading day, fresh reconciliation, explicit human approval in order; every fill/order and a 1-5 second active-scope timer. Exact identity and trusted provider choices remain missing. See [review 011j](human-review-011j.md).

Latest owner/provider declaration: CESAR NIETO PADILLA, external user ID cesar.nieto@outlook.com; Webull OpenAPI market data and account API; NYSE published holidays/early closes. See [review 011k](human-review-011k.md). Identity is declared, not externally authenticated; email is not a brokerage account ID. Source selection is recorded, qualification remains pending. Earlier missing-input statements above are historical.
