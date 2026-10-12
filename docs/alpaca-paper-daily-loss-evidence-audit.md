# Daily-loss evidence audit after source deferral

Daily-loss evaluation now verifies that the retained baseline belongs to the
current New York calendar day, even if a record was incorrectly filed under
today's key. It also blocks P&L computation when the broker account is blocked.
The daily_pnl_evaluated field distinguishes unavailable P&L from an evaluated
non-breach; daily_loss_breach=false alone is never a safety or admission claim.

Validation: 39 targeted daily-loss, activity, boundary-source, observer, event
and process-supervision tests passed. Two new cases cover a prior-day baseline
under the current-day key and a blocked account. Lint, JSON source digests and
git diff whitespace checks passed. No broker mutation or runtime activation occurred.

The owner selected Alpaca-only status, fail-closed, and deferred Nasdaq until
before live-money phases or individual-stock trading. The INTC frozen trial
therefore remains disabled. A new scope question is pending: prepare an ETF-only
plumbing trial with the existing budget/limits, or retain disabled INTC and
read-only preparation. No ETF, replacement symbol or new strategy was selected
by a general instruction to proceed. Historical frozen strategies remain intact.

Readiness remains 23/36 (64%). Status qualification, daily-flow reconciliation,
authenticated resets, global timer/persistent service integration and real paper
broker acceptance remain incomplete. The month trial has not started.
