# Phase v1.0 — human review and approval decisions

**DESIGN COMPLETE / AWAITING HUMAN APPROVAL.** No policy value has been activated. The [approval draft](risk-policy-proposal-v10.md), [numerical register](examples/risk-policy-v10/proposed-numerical-limits.json), and [approval checklist](examples/risk-policy-v10/approval-checklist.json) are the review package. Completion of this design grants no paper or live authority.

The current policy already has the $160 experimental cap; AAPL/MSFT/SPY new-buy allowlist; whole-share BUY LIMIT/DAY/CORE form; no margin, options, shorting or leverage; mandatory theses, kill-switch check, reconciliation, and per-order human review. Actual daily and cumulative loss amounts, age/timezone, hard position and concentration limits, and independent portfolio exposure maximum remain undefined. They fail closed where required. The v0.9 24 synthetic diagnostics replayed exactly, but did not exercise a broker.

The proposed future sleeve is **$1,000**, subject to funding, attribution and approval. Proposed unapproved limits are **$250/25%** maximum single position (lesser with current sleeve equity and available cash), **25%** of sleeve equity maximum same-name exposure, **75%** aggregate sleeve exposure, **$25** minimum order, **lesser of $20 or 2%** start-of-day sleeve equity daily loss, **lesser of $100 or 10%** initial funded sleeve cumulative loss, **30 seconds** quote age, **60 seconds** portfolio-snapshot age, and **5 minutes** approval lifetime. The rationale is bounded capital-at-risk and operational freshness, not tuning historical returns. All are `PROPOSED_REQUIRES_APPROVAL`; the production/whole-account daily stop is still **UNRESOLVED**, not $20 by implication.

The position cap would reject a $500 whole share even with $1,000 cash; no automatic strategy sizing change or fractional order is proposed. A 25%-of-sleeve-equity hard name cap prevents near-total sleeve allocation, while reporting deployed-gross concentration separately. The v0.8 98.83% observation remains exploratory. Daily flow-adjusted realized/unrealized P&L resets at the New York session boundary only after reconciliation and human reset of a latched switch; cumulative sleeve loss remains anchored to its approved baseline across deposits and days. A separately defined account-wide daily stop is required before any production path.

Future atomic PostgreSQL reservations would lock cash and sleeve inventory across concurrent proposals, persist partial-fill commitments, and release only verified terminal amounts. Trusted quote and exchange-calendar inputs would be checked at review and again before future submission. An active kill switch blocks new orders across restarts; canceling existing orders requires a distinct authenticated procedure, and there is no automatic liquidation. Human approval binds one digest and cannot override risk or survive material proposal/state changes.

Human decisions requested: approve/reject each proposed numerical limit and denominator; confirm actual $1,000 funding/attribution separately; define a whole-account daily-loss threshold and portfolio exposure/diversification rules; decide data-outage versus persistent kill-switch behavior and any exception authority; approve clock/quote/session sources and operational ownership; then authorize a distinct v1.1 implementation project if desired. Forward paper additionally needs historical/corporate-action qualification, implementation tests, and separate authorization to start 60 sessions. Human-approved live trading needs further broker/security/reconciliation/recovery qualification and explicit live authorization.

| Required final state | Result |
| --- | --- |
| v1.0 | DESIGN COMPLETE / AWAITING HUMAN APPROVAL |
| Current cap / proposed capital | $160 UNCHANGED / $1,000 NOT APPROVED |
| Proposed limits / production daily stop | NOT ACTIVATED / UNSET FAIL CLOSED |
| v1.0.0 strategies / H01 / H02 | UNCHANGED / EXPLORATORY ONLY / DEFERRED |
| Historical qualification / both strategies | BLOCKED / NOT_ELIGIBLE |
| 2026 OOS / forward paper | SEALED / 0/60 |
| Paper / production / broker submissions | DISABLED / DISABLED / NONE |

No current policy, strategy definition, Risk Engine, or broker integration was modified. Stop after v1.0 for human approval; do not begin v1.1 or activate this draft.
