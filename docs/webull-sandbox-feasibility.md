# Webull retail sandbox feasibility — October 7, 2026

The owner explicitly authorized sandbox evaluation using the private `webull.sandbox.env` file. This authorizes credential use for feasibility checks, not account funding changes, subscription purchases, a migration release, paper orders or live trading. The fixed-host read-only probe is [evaluate_webull_sandbox.py](../scripts/evaluate_webull_sandbox.py); it suppresses SDK request/response logging and puts SDK log files outside the repository. Raw responses and identifiers remain private.

## Actual observations

- Sandbox account authentication returned HTTP 200 and five account records.
- Cash and margin equity-account balance, position, open-order and cash-activity reads all returned HTTP 200. Both equity accounts have simulated USD 1,000,000 equity/cash, no positions and no returned open orders. Open-order query success does not prove instant completeness.
- The cash account includes a `settled_cash` balance field; the margin account does not. This is a schema observation, not qualification of its as-of timestamp or settlement correctness.
- SCHB instrument, snapshot and depth reads returned HTTP 200. The instrument status was OC and the snapshot trading field was RTH. Their presence is not proof of authoritative current halt status. No delay/entitlement qualification is inferred from a successful response.
- The account ID written in the private file matched none of the returned accounts. No account was bound or selected, and the private file was not modified.
- No order preview, submission, cancellation, subscription purchase or account mutation was performed. Alpaca's ledger, disabled observer task and approved limits remain intact.

Sanitized observations and source digests are retained in [the feasibility record](examples/webull-sandbox/feasibility.json). Authentication/data-query feasibility passes. A Webull trial has not been qualified or started.

## Provider capabilities and remaining qualification

The [official SDK environment matrix](https://developer.webull.com/apis/docs/sdk/) specifies distinct retail sandbox HTTP, event and market-data hosts. [Retail trade events](https://developer.webull.com/apis/docs/reference/custom/subscribe-trade-events/) document gRPC order updates and subscription/heartbeat/error events. The reviewed retail interface does not establish the required missed-event replay contract; Broker API cursor documentation cannot be substituted for retail access.

Webull documents [retail cash activities](https://developer.webull.com/apis/docs/reference/trade-cash-activity-by-type/). Successful activity reads still require pagination, publication/correction and coherent balance-boundary qualification before flow-adjusted daily-loss enforcement can be accepted.

The [market-data FAQ](https://developer.webull.com/apis/docs/market-data-api/faq/) distinguishes OpenAPI subscriptions from mobile/desktop subscriptions, explains that MQTT subscriptions need re-establishment after disconnect, and describes delayed sandbox data and corresponding production OpenAPI entitlements. This evaluation did not establish an active real-time entitlement. No subscription should be bought solely on the basis of HTTP 200 responses.

## Next owner action

Choose the retail cash or margin equity sandbox account; cash is recommended for the cash/settlement controls trial. The owner subsequently [approved using actual available whole-account sandbox equity](webull-sandbox-equity-amendment.md), superseding the USD 1,000 whole-account requirement. The separate USD 1,000 experimental sleeve ceiling remains. Confirm the correct ID locally in the credential file using `AIL_WEBULL_ACCOUNT_ID`; do not paste IDs or secrets in chat. Account resetting or funding changes were not attempted.

After account selection and baseline preparation, bind a separate Webull ledger and qualify the adapter, source contracts, protected reset boundary and paper order runtime. Historical Alpaca preparation remains 23/36 (64%); that percentage is not transferred to Webull. Live permission, trial activation and forward-session credit remain unchanged and disabled.

Cash-selection follow-up: the owner chose “Cash”. The unique retail cash equity account is selected in a private, nonoverwriting account-binding record. Fresh bracketed reads again show USD 1,000,000 equity/cash, empty positions and no returned open orders. [Selection evidence](examples/webull-sandbox/cash-account-selection.json) retains the source's settled/unsettled cash observations. No provider coherence, settlement or midnight-baseline qualification is inferred. A separate qualified Webull ledger/runtime remains to be implemented; the credential file and Alpaca ledger were not changed.

Current continuation: [the unblock plan](webull-trial-unblock-plan.md) supersedes the original account-selection and USD 1,000 whole-account blockers. Independent engineering can proceed; the immediate owner input is existing Non-Display OpenAPI entitlement status. Required provider evidence and runtime/reset work are listed separately.
