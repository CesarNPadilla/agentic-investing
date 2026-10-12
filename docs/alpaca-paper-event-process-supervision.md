# Process supervision of read-only event checks

The parent watchdog now launches only the fixed paper event observer module with explicit private input paths. The child emits bounded newline-delimited receipts after durably completed startup, fill/order or timer checks. Receipts must have ordered sequence numbers, successful account observation and disabled execution/trial flags. Quiet transport alone does not extend the check deadline. A final result must agree with the completed-check count and the process must exit successfully.

The parent waits at most five seconds for the next completed-check receipt and bounds total child duration. Late, malformed, out-of-sequence, failed or activation-enabled state is rejected. A stalled read-only child is terminated before the durable watchdog failure latch is written. The session claim is persisted before launch; failed or abandoned sessions block automatic relaunch and require a separately scoped recovery. The earlier quote-check acknowledgement does not authorize recovery of this watchdog.

An actual bounded five-second monitor completed three startup/timer checks against the dedicated paper account. Cash and positions matched, the quote was read, and every accounting/status/reset/runtime blocker remained. No orders were submitted or paper-trial session counted. Fixture tests use actual subprocesses to verify hung-child termination, restart refusal, normal completion, malformed output and sequence rejection.

This qualifies bounded process/event integration, not a persistent service or a global hard real-time guarantee. Parent process creation, SQLite access and durable persistence can still take time. Parent-crash orphan handling, operating-system service installation, reconnect/gap recovery, ongoing security-status integration and reporting remain incomplete. The month trial is unstarted; live execution remains unauthorized. The historical 23/36 acceptance snapshot is not promoted.

To repeat the bounded read-only check:

Later qualification: [parent-crash containment](alpaca-paper-parent-crash-containment.md) adds a Windows job and a bounded gate before source access. The earlier absence of parent-crash child containment is superseded for this entry point; recovery of the abandoned parent session and persistent deployment remain unqualified.

```powershell
.\.venv\Scripts\python.exe -m scripts.supervise_paper_events --env-file 'C:\Users\cesar\AppData\Local\AgenticInvesting\alpaca-paper-trial.env' --ledger-file 'C:\Users\cesar\AppData\Local\AgenticInvesting\alpaca-paper-fill-ledger-v1.sqlite' --owner-credential-file 'C:\Users\cesar\AppData\Local\AgenticInvesting\owner-passkey-enrollment.json' --seconds 5
```
