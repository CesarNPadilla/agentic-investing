# Read-only observer deadline and restart controls

The bounded observer CLI now dispatches each source cycle through a five-second
deadline. On timeout it discards the eventual result, stops the requested cycle
sequence, and persists OBSERVER_DEADLINE_MISSED in the private account-bound
SQLite state. A subsequent CLI invocation refuses further reads while that
reason is present. There is no automatic reset or latch release.

The reader thread may still finish its read-only broker requests and ledger
bookkeeping after timeout. No second cycle is dispatched by this invocation.
The persistent latch remains sticky across subsequent ledger observations.
Storage failure returns an additional sanitized persistence blocker. If storage
fails, durable restart protection cannot be asserted; recovery must inspect the
service and state before reuse. No credential or private provider error is output.

This is not a qualified hard trading watchdog: the SQLite latch can wait for a
transaction lock, process supervision is absent, and order/fill event monitoring
is unfinished. Runtime execution remains unavailable. No paper order was sent
and the month trial has not started.

Validation: 34 targeted tests passed, including a genuinely blocked reader,
late-result rejection, durable timeout recovery, restart refusal, persistence
failure, existing order reservations, and plumbing intent sequencing. Lint and
git diff whitespace checks passed. A new evidence snapshot records source hashes;
previous evidence snapshots remain historical and are not rewritten.

Acceptance readiness remains 21/36 (58%): account 100%, plumbing 75%, quotes and
calendar 75%, status and clock 50%, reconciliation and settlement 75%, loss/reset
50%, paper order lifecycle 75%, continuous runner 25%, trial launch 0%.
Clock-policy approval remains outstanding; no general continuation instruction
is recorded as approval of a particular clock-error tolerance.
