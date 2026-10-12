# Durable plumbing intent sequence

Intent preparation now commits the frozen 1.1.0 daily claim and original intent
together in the existing account-bound SQLite transaction. Restart exposes an
unsubmitted claim for recovery rather than repricing it or preparing another.
Only durable fills matching broker identities of this strategy's claims establish
ownership. Receipt quantities must exactly match the fill ledger; unresolved
orders block further intent preparation. Other holdings are not attributed to
the trial. No broker submission is performed by this component.

Tests cover restart, immutable prepared prices, foreign holdings, missing fills,
owned-share exits, same-day re-entry prevention, and next-day entry after restart.
The complete sequence is verified with local fixtures. Its connection to the
continuous runner, reservation reconciliation, actual market-status controls and
all risk gates remains unfinished. Caller-supplied observation qualification is
not an execution permission. Existing execution flags and policy are unchanged.

Readiness remains 21/36 (58%); no acceptance credit is claimed for this partial
integration. The month trial has not started. Clock-error policy approval is
still outstanding; other engineering work can continue independently.
