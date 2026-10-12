# Readiness to start the one-month plumbing trial

**50% of the acceptance checklist complete: 18/36 criteria.** This is a curated evidence inventory, not a time/effort estimate or launch authorization. Remaining order/runtime work may require more effort than completed preparation. Every required criterion must pass.

| Step | Complete | Accepted criteria |
| --- | ---: | ---: |
| Account and baseline | 100% | 4/4 |
| Plumbing strategy | 75% | 3/4 |
| Quotes and calendar | 75% | 3/4 |
| Status and clock | 50% | 2/4 |
| Reconciliation and settlement | 75% | 3/4 |
| Loss stops and resets | 50% | 2/4 |
| Paper order lifecycle | 0% | 0/4 |
| Continuous runner | 25% | 1/4 |
| Trial launch | 0% | 0/4 |

Acceptance criteria, in the same order:

- Account: dedicated $1,000 account; authenticated paper keys; empty/unblocked account; initialized private bound ledger. All verified.
- Strategy: frozen ID/version, INTC universe and bounded intent tests pass; complete buy/exit/reentry lifecycle remains unfrozen.
- Quotes/calendar: real IEX bid/ask, fail-closed timestamp/price tests and bounded NYSE schedule pass; integrated decision-time qualification remains.
- Status/clock: transition tests and real stream subscription pass; initial status/continuous health and approved/qualified clock remain.
- Reconciliation: durable fills, fee/flow/quantity checks and approved paper settlement model pass; coherent cutoff/late-publication qualification remains.
- Loss/reset: fixture arithmetic and durable blocked state pass; actual runtime baselines/monitoring and externally authenticated resets remain.
- Orders: fixed paper adapter, persisted uncertain-submit handling, fill/cancel/reservation integration and end-to-end recovery tests remain.
- Runner: one real read-only cycle passes; event/timer loop, service recovery and month-expiry/daily reports remain.
- Launch: integrated acceptance run, controlled paper round trip, persistent deployment with dates and first qualifying session remain.

This turn obtained a real authenticated IEX status subscription acknowledgment for INTC using the dedicated paper keys. The bounded read-only probe connected, authenticated, subscribed and closed. No order/account mutation or raw credential payload logging occurred. Initial current status and continuous health were not verified. [Alpaca's stream protocol](https://docs.alpaca.markets/us/docs/websocket-streaming) documents authentication/subscription; acknowledgment is not current-status proof.

Added an optional paper dependency group; websockets 15.0.1 is installed in the existing project virtual environment. No paid subscription or SIP upgrade was purchased. **130 targeted tests passed**, including two stream-probe tests for handshake/subscription and sanitized errors.

Next priority is integrated paper order lifecycle and the continuous runner. Pending owner clock-source/error policy remains open. General proceed instructions do not fill that numerical policy choice. One-month paper permission is already recorded; it does not need repeating. No start/end date is invented, no execution flag changed and forward paper remains 0/60. Live authorization stays separate.
