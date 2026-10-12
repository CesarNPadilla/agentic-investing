# Current paper-trial preparation assessment — October 7, 2026

**Preparation component checklist: 64% (23/36). Trial launch: 0%.** The [v6 assessment](examples/alpaca-paper-month/trial-readiness-progress-v6.json) explicitly lists all 36 criteria, replaces the historical INTC strategy evidence with SCHB ETF evidence, and conservatively retains the previous category totals. This percentage measures accepted preparation components, not time remaining or permission to trade. Historical account and clock observations still require fresh runtime verification.

| Step | Component completion |
| --- | ---: |
| Account and initial baseline | 100% |
| ETF plumbing strategy | 100% |
| Quotes and calendar | 75% |
| Status and clock | 75% |
| Reconciliation and settlement | 75% |
| Loss stops and resets | 50% |
| Paper order lifecycle | 75% |
| Continuous runner | 25% |
| Trial launch | 0% |

The next crash qualification now kills an actual disposable diagnostic-service process after its durable RUNNING record is committed. A subsequent invocation refuses source access and returns RECOVERY_REQUIRED; it retains the unfinished record and the risk latch. This verifies interrupted-service rejection, not authenticated recovery. It does not touch the real account or private ledger. The existing parent/child containment tests cover the separate event-process boundary. Together these components still do not establish continuous source coverage or complete service recovery.

Validation: 313 selected tests pass. The installed Windows task remains disabled. Source digests and JSON are validated; no trading flags, limits, historical/OOS evidence or credential files were changed. No provider requests were sent.

The next external dependency is [the prepared Alpaca evidence request](alpaca-paper-provider-evidence-questions.md): startup status/halt coverage, disconnect replay, activity publication, coherent snapshot boundaries and opening funding-journal timing. Independent owner risk-reset protection and real paper order-runtime qualification also remain open. Provider answers can inform implementation; they do not automatically approve a policy exception. The month trial has not started; forward evidence remains 0/60 sessions and live trading is unauthorized.
