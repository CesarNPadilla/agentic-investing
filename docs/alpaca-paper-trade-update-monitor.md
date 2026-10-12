# Read-only paper order/fill event monitor

The new bounded monitor connects only to the paper account websocket, authenticates
with the external paper credentials, and requires an explicit trade_updates
subscription acknowledgment. It supports JSON in binary frames and rejects
malformed/unexpected responses. Only auth and listen messages are sent; no order
submission or cancellation path exists.

The real 10-second probe authenticated, subscribed, and completed with zero
order/fill events. A quiet connection was checked with matching websocket pong
responses. No actual fill handling or event-driven risk qualification is inferred.
The subscription closes when the bounded probe completes.

Fixtures verify that every received update invokes the supplied callback,
including partial-fill and cancellation events. Callback failure stops the
probe and omits private exception details. Optional cooperative timer callbacks
are dispatched during quiet streams. They are not a hard watchdog: socket waits
and callbacks can delay dispatch, and persistent supervisor/restart behavior and
independent timer enforcement remain unqualified. No callback grants execution
permission or changes the durable fill ledger automatically.

Reference: [Alpaca websocket streaming](https://docs.alpaca.markets/us/docs/websocket-streaming)
documents the separate paper account endpoint, authorization, listen acknowledgment,
binary frames, and trade-update event types.

Readiness remains 23/36 (64%). Event-stream connectivity is useful preparation,
but does not complete the continuous runner acceptance criterion. Initial trading
status, reconciliation completeness, authenticated resets, full runner supervision
and real paper order acceptance still block launch. The Nasdaq supplemental-source
decision remains pending. No orders were sent and the month trial has not started.
