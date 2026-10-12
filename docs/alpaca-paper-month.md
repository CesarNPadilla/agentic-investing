# Alpaca one-month paper trial preparation

The owner explicitly requested one month of Alpaca paper trading, then selected **prepare account and controls first**. [Trial plan](examples/alpaca-paper-month/trial-plan.json) records that authorization without inventing a decision timestamp or strategy. No repeat paper permission is required for this scope once prerequisites are satisfied. Live execution is not authorized.

A read-only preflight on the configured external Alpaca credential file passed: account ACTIVE, all three block flags false, zero positions and zero open orders. No balance, account identifier, credential or provider response was written to the repository. Webull credential fields are present at the owner-specified external path; this does not by itself verify API authentication or market-data entitlement.

The paper-only preflight hardcodes https://paper-api.alpaca.markets, rejects redirects, and has no mutation methods. To repeat locally:

```powershell
.\.venv\Scripts\python.exe -m scripts.check_alpaca_paper --env-file 'C:\Users\cesar\AppData\Local\AgenticInvesting\alpaca.env'
```

The trial uses a $1,000 simulated sleeve budget with the existing N01-N10 controls, separate whole-account 1% start-of-day daily loss and 100%/10% current-equity exposure limits. Do not pretend the default paper balance is $1,000: account baseline and sleeve attribution must be reconciled explicitly, and no existing account reset is authorized or performed. A dedicated $1,000 simulated account can provide closer capital realism if selected later. No automatic policy relaxation is implied by paper execution.

[Alpaca paper trading](https://docs.alpaca.markets/us/docs/paper-trading) is free; paper-only accounts receive IEX data, while simulated fills use NBBO. Record that feed/fill difference, missing market impact, latency slippage, dividends and regulatory fees in trial reporting. The current last-trade adapter is insufficient for the approved bid/ask/freshness/status evidence contract; source and runtime control integration remain required.

The one-calendar-month window begins at actual qualified startup, not this preparation date. Freeze the strategy/version and symbols before startup. Implement a persistent paper-only runner with idempotent order identifiers, reservation/fill reconciliation, sticky loss stops, externally authenticated reset, every-fill/order checks and bounded 1-5 second monitoring. Integrate the selected NYSE calendar and restart/outage behavior before submitting orders. At expiry, block new entries and report open holdings/orders for human review; do not silently liquidate them. A chat turn is not a month-long runtime.

Report returns, benchmark comparison, costs, drawdown, volatility, completed-trade statistics, agent reasoning, risk blocks, data gaps, reconciliations and uptime. Count actual qualifying forward sessions only; missing observations remain missing. One month does not replace the existing 60-session qualification requirement or grant live permission. 2026 OOS remains sealed.

Validation: 20 preflight/readiness tests passed, including fixed paper host, redirect/auth/quota failures, private-data omission and nonempty account handling. Plan JSON and source digests validate; git diff --check passes. Account preparation has begun; broker paper trading and the trial clock have not started.

Webull follow-up: authenticated read-only account listing now succeeds using the supplied external credential file. Only response shape was displayed, with no private values. This verifies account-list API access, not market-data entitlement, target-account binding or live release. The existing strategy experiment example is synthetic, BACKTEST-only and contains UNSET controls; it is not a frozen broker paper strategy. Account preparation remains complete to the verified preflight boundary; strategy/control integration and the persistent runner remain outstanding.

Quote preparation: [bid/ask reader and validation](alpaca-paper-quote-controls.md) implemented; real IEX read succeeds, closed-market stale quote blocks, status remains unverified. 33 targeted tests pass. Runtime/control integration remains pending.

Calendar preparation: [NYSE schedule adapter](alpaca-paper-calendar-controls.md) now handles bounded 2026 coverage, holidays, early closes, DST and next-trading-day lookup. 67 targeted tests pass; extraordinary closures/status/clock and runtime integration remain pending.

Latest: [combined preparation review](alpaca-paper-control-pipeline.md) records the owner-selected plumbing strategy and dedicated $1,000 account. Historical unselected-strategy statements above are superseded for intent generation; a complete execution strategy/runtime is still pending.

Fill preparation: [activity acquisition/replay review](alpaca-paper-fill-controls.md) records bounded read-only acquisition and 94 passing targeted tests. The dedicated account baseline is verified; historical baseline-mismatch statements are superseded by dedicated-account-recheck.json. Settlement/order lifecycle/runtime work remains incomplete.

Durable fill step: [ledger review](alpaca-paper-durable-fills.md) records replay/restart/concurrency tests and private dedicated-account initialization. Fees/flows/settlement and execution runtime remain pending.

Cash step: [fee/flow and cash review](alpaca-paper-cash-controls.md) adds explicit deposit/withdrawal scope and conservative date handling. 108 targeted tests pass; observed balance equality does not qualify settlement or runtime execution.

Latest combined work: [quantity, settlement and clock review](alpaca-paper-settlement-clock.md). Owner approved explicit paper settlement assumptions; 118 targeted tests pass. Windows resync succeeded, but proposed one-second uncertainty bound remains blocked and awaiting owner selection. No trial startup.

Status step: [independent status controls](alpaca-paper-status-controls.md) handle tape-specific transitions and connection loss without inferring active status from quote/calendar success. 128 targeted tests pass; real stream and execution runtime remain pending.

Current readiness: [order lifecycle review](alpaca-paper-order-lifecycle.md) and progress v2 update overall checklist to 56%, order lifecycle to 50%. Percentages describe component acceptance, not launch authorization.

Current progress v3: [reservation integration and observer](alpaca-paper-integrated-observer.md), 58% checklist, 143 targeted tests passed. Actual order mutations and month startup remain blocked.

Current acceptance snapshot is [progress v5](examples/alpaca-paper-month/trial-readiness-progress-v5.json): 23/36 (64%), including the [passing clock evidence](alpaca-paper-clock-qualified.md). Later [midnight source](alpaca-paper-midnight-status-integration.md), [daily activity](alpaca-paper-daily-activity-integration.md), [event risk integration](alpaca-paper-event-risk-integration.md), and [event recovery audit](alpaca-paper-event-recovery-audit.md) strengthen components without claiming additional complete runtime gates. The owner has selected [Alpaca-only status, fail-closed, and deferred Nasdaq](examples/alpaca-paper-month/status-source-decision.json). Nasdaq is required before live-money phases or individual-stock trading; the existing INTC plan therefore remains blocked without any replacement security selected. No paper orders or month trial have started. Earlier progress snapshots are historical.

The owner subsequently selected [ETF-only plumbing scope and explicitly kept INTC disabled](examples/alpaca-paper-month/etf-scope-decision.json). The $1,000 dedicated paper account and all existing limits remain. ETF selection, asset/feed qualification and a new frozen strategy version are pending; the historical INTC implementation is not silently relabelled. Alpaca-only status remains fail-closed and Nasdaq deferred. Scope selection does not clear launch gates or start the trial.

ETF follow-up: [SCHB intent freeze](alpaca-paper-etf-freeze.md) selects an issuer-confirmed ETF and verifies Alpaca active/tradable asset status. The new ETF-only 1.0.0 intent model preserves limits and distinct identifiers; INTC remains disabled. The actual pre-open IEX quote had a zero ask and was rejected. ETF durable ownership, routing and runtime qualification remain pending; no trial startup or readiness increase is claimed.

ETF integration: [durable ownership, restart fixtures and diagnostic routing](alpaca-paper-etf-integration.md) are now implemented for SCHB. Actual status subscription succeeds but initial status remains UNKNOWN. Today's midnight baseline is retained. A startup quote failure left an unfinished event journal and the service latched; authenticated owner recovery is required before that monitor resumes. The separate owner authentication mechanism is awaiting selection. No journal evidence was discarded, no latch cleared and no trial started.

Owner authentication update: Windows Hello/passkey in a separate local app is selected. The [enrollment/authentication prototype](alpaca-paper-owner-passkey.md) is ready for the owner's direct interaction. It grants no recovery or execution authority; external-reset qualification remains pending.

Enrollment follow-up: [the private enrollment is confirmed](alpaca-paper-owner-enrollment-check.md). Authentication tests now retain signed verification evidence privately; the initial prototype did not persist the earlier test. Repeat **Test my passkey** with the existing enrollment to produce verifiable evidence. This does not approve recovery or start trading.

Real verification follow-up: [the saved owner assertion](examples/alpaca-paper-month/owner-real-verification.json) cryptographically verifies against the enrolled credential with required user verification. The previous request to repeat the test is satisfied. [A new regular-session SCHB quote](examples/alpaca-paper-month/etf-regular-session-quote.json) passes positivity/freshness checks; initial market status and runtime integration remain unverified. The authentication proof covers a test only; action-bound owner recovery approval and independently protected reset authority remain pending. The unfinished journal, all latches and execution flags remain unchanged.

Scoped recovery step: [the signed read-only restart review and controller](alpaca-paper-readonly-recovery-review.md) are prepared and fixture-qualified. The owner app displays the actual failed-check plan for a passkey signature. The separate controller can acknowledge that exact failed check after fresh empty-account comparison while preserving the original failure and every risk latch. No actual signature or acknowledgement has been invented or applied; trading and the trial remain disabled.

Recovery follow-up: [the owner's actual scoped signature was verified and applied](alpaca-paper-recovery-completed.md). The original failure and all risk latches remain; bounded read-only event/timer observation resumed successfully with three diagnostic cycles. No new unresolved journal failures remain. Executed USD cash journals are now classified conservatively, but the actual baseline-day journal remains ambiguous. Publication/flow/status/reset-authority and persistent-runtime gates still block trading and trial startup.

Event-process follow-up: [the watchdog now supervises the read-only fill/order/timer observer](alpaca-paper-event-process-supervision.md). An actual bounded run completed three checks with cash and positions matching; 296 selected tests passed. Failed/abandoned parent sessions and stale or malformed check receipts block restart. Persistent service and reconnect/parent-crash recovery remain incomplete; no trial startup or readiness promotion occurred.

Parent-crash follow-up: [Windows child containment and a bounded startup gate](alpaca-paper-parent-crash-containment.md) now protect the process-supervised event monitor. An actual parent-death test verifies child termination; a dedicated-account run completed three checks. 299 selected tests pass. Crashed sessions still require recovery; persistent service, reconnect, status/accounting and independent risk-reset gates remain pending. No orders, latch release, trial start or readiness promotion.

Connection follow-up: [durable connection records and checks after authentication](alpaca-paper-connection-checkpoints.md) now prevent event dispatch before a fresh source diagnostic. Interrupted/failed records block restart; normal bounded windows never establish continuous event coverage. The actual run completed four diagnostics; 303 selected tests pass. Automatic replay/gap recovery, persistent service, initial status, accounting and protected reset gates remain unqualified. No trial startup or readiness promotion.

Launch evidence audit: [the remaining gates](alpaca-paper-launch-evidence-audit.md) now distinguish provider/owner evidence from engineering work. [Precise Alpaca support questions](alpaca-paper-provider-evidence-questions.md) cover initial status, gap coverage, activity publication, coherent as-of boundaries and opening journal timing. The reviewed docs do not establish those guarantees. Current policy is unchanged; historical readiness percentages are not promoted and no trial begins.

Service preparation: [the windowed read-only service](alpaca-paper-readonly-service.md) now records durable runs and stops on failed or abandoned sessions. Its Windows task is installed disabled with no triggers or automatic retries. A dedicated-account two-window diagnostic completed eight source checks; 312 selected tests pass. Connection gaps remain unqualified and all launch blockers remain. No background task, trading trial, or live execution was activated.

October 7 assessment: [current preparation progress](alpaca-paper-readiness-current.md) is conservatively 64% (23/36 explicit component criteria), with launch at 0%. SCHB evidence replaces historical INTC strategy evidence. An actual disposable service-crash test confirms durable restart refusal without source access; 313 selected tests pass. The task remains disabled; complete source coverage, protected resets and paper order runtime remain pending. No month trial or live trading started.

Backup follow-up: [a private diagnostic snapshot](alpaca-paper-diagnostic-backup.md) is verified with source read-only access and no broker calls. Original latches and unfinished records are retained; existing backups cannot be overwritten. 318 selected tests pass. This does not qualify protected disaster recovery or authorize restore; preparation remains 64%, launch 0%.
