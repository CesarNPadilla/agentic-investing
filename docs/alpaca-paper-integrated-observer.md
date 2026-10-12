# Reservation/fill integration and combined paper observer

**Checklist: 58% (21/36 accepted criteria). Order lifecycle: 75%. Runner remains 25%.** [Progress v3](examples/alpaca-paper-month/trial-readiness-progress-v3.json) preserves prior snapshots. Percentages are equal-weight component acceptance, not estimated time or launch permission.

| Step | Complete |
| --- | ---: |
| Account and baseline | 100% |
| Plumbing strategy | 75% |
| Quotes and calendar | 75% |
| Status and clock | 50% |
| Reconciliation and settlement | 75% |
| Loss stops and resets | 50% |
| Paper order lifecycle | 75% |
| Continuous runner | 25% |
| Trial launch | 0% |

Broker order IDs now bind client intents, validated receipts and durable fills. Buy reservation reconciliation requires exact account/client/broker identity, symbol, side, fill quantity and limit-price bounds. Consumed cost remains held; unfilled cost releases only after terminal status matches the durable fill ledger. Partial fills retain pending costs. Cancel acknowledgment or missing ledger fills release nothing. Replay is idempotent. Sell intents reserve existing unpledged shares instead of cash, block competing oversells and report proceeds as unsettled; they do not replenish usable cash. Mapping to the common fill ledger allows the separate owner-approved paper settlement model to schedule sale release. Acquisition consumption is not silently rebased after sales.

Real POST/DELETE remain hard blocked; order mutations occur only in httpx.MockTransport fixtures. Tests cover partial fill/cancel/release, missing terminal fills, broker identity, share reservations and isolated lifecycle replay. End-to-end real broker execution and runner recovery remain required; fixture success cannot clear them.

The new integrated read-only observer brackets account inventory, imports overlapping activities into the private ledger, refreshes account quantities, reads INTC quote/calendar, compares cash/positions, computes the paper settlement model and checks Windows Time. It records blockers and applies conservative cumulative-loss/gross/security diagnostics. The NY midnight daily baseline and external reset are still unqualified; no synthetic evidence is relabeled as real. Paper settlement is modeled independently, while the general reconciliation's settlement/publication flags remain conservative.

A bounded timer wrapper completed two authenticated five-second real cycles with cash and quantities matching the ledger. It runs no order socket, fill-event subscription, month-long daemon or service deployment. Deadline overruns are flagged after the read cycle; this is not the independently enforced hard timer required for active trading. Active scopes configured above five seconds also block. Therefore the event/timer runtime criterion remains incomplete and runner percentage stays 25%. All private state remains outside the repo. No trial start or qualifying sessions are recorded.

Windows status during the real cycles showed a stale last good sync exceeding the poll interval and sync error 2. Clock policy remains unapproved; the source/error-bound question is still pending. This is a genuine qualification blocker, not resolved by general proceed instructions. Clock check, source bootstrap, coherent publication/cutoffs, actual daily-loss/reset and complete runner remain required. No local clock configuration was changed this turn.

Validation: **143 targeted tests pass**, including six new reservation/observer tests; Ruff checks, source digests/new progress JSON and git diff --check pass. Prior code-source digests stay historical when implementations evolve; the current progress package captures current sources.

To repeat one read-only integrated cycle:

```powershell
.\.venv\Scripts\python.exe -m scripts.observe_paper_trial --env-file 'C:\Users\cesar\AppData\Local\AgenticInvesting\alpaca-paper-trial.env' --ledger-file 'C:\Users\cesar\AppData\Local\AgenticInvesting\alpaca-paper-fill-ledger-v1.sqlite'
```

Continue independent integration work while the clock decision is pending; startup qualification requires resolving that decision and obtaining passing actual clock evidence. No paper/live execution flag changed, no order submitted, 2026 OOS sealed and forward paper remains 0/60.
