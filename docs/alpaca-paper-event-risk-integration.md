# Read-only event and timer risk integration

The paper order/fill stream can now call the existing account, ledger, settlement,
clock and daily-loss observer on every received update and on timer callbacks.
Each check is journaled before dispatch in the private account-bound state, with
its connection epoch, trigger, payload digest, timestamps, completion and blockers.
Raw provider text and credentials are not journaled. Duplicate updates still
trigger checks; they do not independently book cash or fills. Unknown events,
invalid order identities and securities outside INTC latch and stop monitoring.

Risk observation is bounded by a five-second deadline. Timeout discards the late
result, stops further callbacks, and requires recovery on restart. Active-scope
checks also account for elapsed time since the last completed check; an overdue
or regressing timer stops before another read. The remaining deadline is reduced
by elapsed time, including journal preparation. Deadline latches survive restart.
Timer callbacks are requested every second rather than waiting five seconds and
then adding the duration of the risk check.

The actual integrated 12-second monitor authenticated and subscribed, ran startup
and timer risk observations, and recorded them durably. No trade events arrived.
Cash and quantities matched, but daily-flow publication, status, reconciliation,
settlement and runtime gates stayed blocked. No broker mutation exists here.

This remains a bounded serial diagnostic, not a qualified persistent trading
service. Socket waits and callbacks may defer message processing; missed events
across reconnect, independent timer enforcement, process supervision, persistent
recovery and actual broker round-trip acceptance remain unfinished. The deadline
diagnostics do not assert a hard real-time scheduling guarantee. No continuous
runner acceptance credit is claimed for partial integration.

Readiness remains 23/36 (64%). Initial-status source selection still awaits the
owner's Nasdaq decision. The month trial has not started, forward sessions remain
uncounted, and execution flags remain disabled.
