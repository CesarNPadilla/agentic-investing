# Read-only process supervision qualification

A separate parent watchdog now launches only the fixed single-cycle read-only
paper observer, with a maximum five-second child deadline. The command uses
structured arguments, a hidden Windows process, external credential/state paths,
and no shell. It is not a generic broker executor or an order submission watchdog.
Successful child reports must retain execution=false, trial_started=false,
successful account observation and a typed blocker list. Child stderr and invalid
stdout are not surfaced as private provider details.

On timeout the parent terminates the read-only child before attempting a durable
deadline latch. The timeout reason prevents automatic relaunch. An actual hung
child test verifies termination. A second actual child test holds a SQLite write
transaction: termination releases the lock, rolls back unfinished changes and
permits the parent to persist its recovery latch. No late child result is admitted.

Bounded batches retain a session claim before starting children and record completed
cycles. Abandoned or failed sessions block automatic restart and require recovery;
no automatic session deletion or latch release exists. A real two-cycle batch
completed against the dedicated account. Cash and quantities matched; daily-flow,
status, reconciliation, settlement, calendar/quote and runtime gates stayed blocked.

This qualifies process termination and bounded read-only batch recovery only.
Parent state access, process creation and persistence can still take time; no
global hard real-time timer guarantee is asserted. Event-stream integration with
this parent watchdog, persistent service installation, reconnect/gap recovery and
month reporting remain incomplete. No background service was installed and no
paper trading process was launched.

Readiness remains 23/36 (64%). Remaining launch gates also include initial trading
status, publication/snapshot coherence, daily-flow qualification, externally
authenticated resets and actual paper order acceptance. The owner has now chosen
Alpaca-only status, fail-closed, and deferred Nasdaq. Unknown/missing status still
blocks orders. Nasdaq must be added before any live-money phase or individual-stock
trading. INTC is an individual stock, so the existing plumbing plan remains blocked
under that condition; no replacement security was selected. The exact instruction
is recorded in [the source decision](examples/alpaca-paper-month/status-source-decision.json).

The trial is unstarted, no orders were sent, live execution remains disabled and
no forward session was counted. Historical acceptance snapshots are preserved.

The subsequent [ETF-only scope decision](examples/alpaca-paper-month/etf-scope-decision.json)
resolves the replacement instrument category while explicitly keeping INTC disabled.
A qualified ETF and new frozen version still need preparation. The supervisor
does not route orders or reinterpret the historical INTC fixture as an ETF strategy.

Current follow-up: SCHB ETF ownership and routing are prepared. [Bounded event-process supervision](alpaca-paper-event-process-supervision.md) now connects the event/timer diagnostic observer to a parent check-receipt watchdog. This resolves the earlier absence of bounded event-process integration, while persistent service, reconnect and parent-crash handling remain unqualified. No order routing or execution release is added.
