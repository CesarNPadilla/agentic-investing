# Future v1.1 implementation backlog — not started

Each item requires approved policy decisions first. Passing synthetic tests does not authorize paper or live execution.

| Work item | Acceptance criteria and tests |
| --- | --- |
| Approved policy schema | Explicit version/effective time/signature, all denominators and units, incompatible-version rejection, no implicit defaults; schema and migration tests. |
| Deterministic enforcement | Separate sleeve/account loss, position/concentration/aggregate exposure and cash checks; boundary, multi-violation and replay tests. |
| Atomic reservations | PostgreSQL transaction/uniqueness/locking; concurrent double-spend, partial-fill, cancel, reject, disconnect, expiry and restart tests. |
| Trusted quote/session adapters | Source and clock provenance, 30-second quote and 60-second snapshot proposal if approved, holiday/early-close/outage tests; no research data fallback. |
| Snapshot validation | Coherent complete accounts, positions, orders and transactions; stale/missing/corporate-action mismatch tests. |
| Persistent kill switch | Cross-process latch, trigger precedence, human-only reset, restart and outage tests. |
| Daily/cumulative P&L | Flow-adjusted realized/unrealized sleeve and account evidence, NY boundary, fees/deposits, mark gaps and reset tests. |
| Audit and approvals | Immutable event sequence, one-use digest-bound approval, five-minute proposal if approved, policy/state/quote change invalidation tests. |
| Reconciliation/restart | Unknown broker status retains reservation; ledger mismatch freezes entries; receipt and recovery tests. |
| Environment isolation | Separate secrets, accounts, policy and deployment; cross-environment denial and privilege tests. |
| Broker-neutral integration | Capability-normalized order status and errors, idempotent submission contract, sandbox-only test doubles first; independent security and human authorization gate. |

Before forward paper: approved limits, trusted data, reservations/reconciliation, historical qualification and corporate-action gates, separate paper-environment approval, and an explicit decision to start the 60-session clock. Before human-approved live: further broker/security review, operational incident/monitoring tests, production policy and whole-account loss stop, explicit live authorization. Neither milestone follows automatically from v1.0 design approval.
