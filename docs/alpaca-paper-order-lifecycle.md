# Paper order lifecycle - protocol and durable submit qualification

**Trial checklist: 56% (20/36 criteria), up from 50%. Paper order lifecycle: 50%, up from 0%.** Percentages track equally weighted accepted criteria, not effort/time or launch permission. [Progress v2](examples/alpaca-paper-month/trial-readiness-progress-v2.json) preserves the prior snapshot and names the newly accepted implementation/fixture criteria.

| Step | Complete |
| --- | ---: |
| Account and baseline | 100% |
| Plumbing strategy | 75% |
| Quotes and calendar | 75% |
| Status and clock | 50% |
| Reconciliation and settlement | 75% |
| Loss stops and resets | 50% |
| Paper order lifecycle | 50% |
| Continuous runner | 25% |
| Trial launch | 0% |

The new protocol fixes the host to paper-api.alpaca.markets, INTC, whole shares, limit/day orders and no extended hours. The dedicated-account plumbing intent enforces $25-$100 notional; full sleeve/account risk checks are still required before any real order. POST/DELETE are permitted only with httpx.MockTransport; actual mutation is hard blocked. GET lookup is read-only. No real adapter activation or order CLI was introduced.

The lifecycle binds persisted account and client-order identity, atomically reserves capacity and commits SUBMISSION_UNCERTAIN before the first fixture POST. Restart/concurrent replays use [client-order-ID lookup](https://docs.alpaca.markets/us/v1.4.2/reference/getorderbyclientorderid) instead of resubmitting. Timeouts, broker payload mismatches, regressing fills and terminal-state conflicts block. A 404 after uncertainty does not prove no order was accepted and never frees capacity. The protocol validates broker quantities/prices/side/type/client ID. Raw provider errors or credentials are not returned.

Cancellation acknowledgment is not terminal state, settlement or reservation-release evidence. Reservations remain fully held in this implementation; partial/terminal consumed-cost and unfilled-release integration with the fill ledger is still unfinished. The fixture lifecycle does not bypass the persisted initial latch or claim externally authenticated approval. Its ability to call mock transport despite a latch is test qualification only, not a release path.

Validation: **137 targeted tests pass**, including seven new lifecycle tests covering commit-before-network, concurrent single POST, timeout/404, changed IDs, fill regression, wrong symbol, process interruption/restart and cancel acknowledgment. Ruff checks, new progress JSON/source digests and git diff --check pass. Broker credentials were not used for mutations; no actual paper order or daemon started.

Next: integrate consumed/remaining reservation handling, durable real loss/reset qualification and one continuous runner, then perform the controlled paper acceptance round trip once status/clock/reconciliation gates pass. Clock decision and current-status bootstrap remain pending. The month-long trial remains unstarted and live authorization absent.
