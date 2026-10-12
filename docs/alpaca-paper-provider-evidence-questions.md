# Alpaca paper evidence questions

Prepared for the owner to submit through authenticated Alpaca support. This is a controls-only SCHB ETF paper trial using IEX and Trading API paper endpoints. No credentials or account identifiers are included here.

**Who answers:** Alpaca's support/API team provides the technical answers. The owner submits this request through their authenticated support channel and shares the response here; the engineering agent evaluates it. This request has been prepared, not sent. Do not include API keys or secrets.

**Suggested subject:** Trading API paper / IEX SCHB: status bootstrap and accounting evidence contracts

**Current priority:** The owner authorized a [Webull sandbox feasibility evaluation](webull-sandbox-feasibility.md) instead of continuing to wait for Alpaca support. This request remains unsent and deferred during evaluation. Its unresolved guarantees remain unresolved; no provider switch or exception has been activated.

**Next actions now belong to Webull preparation:** see the [current unblock plan](webull-trial-unblock-plan.md). The cash account is selected, and its actual available equity replaces the sample whole-account USD 1,000 requirement. This deferred Alpaca request is not the next required owner action.

1. After subscribing to IEX `statuses` for SCHB, how can a client establish its current security trading status at startup? Does the subscription supply an initial snapshot, or only subsequent events? Please identify a supported endpoint/message and coverage guarantee. We cannot treat a quiet subscription, a tradable asset flag, a current quote or an open market clock as proof that the security is not halted.
2. Does IEX status delivery cover the applicable exchange/regulatory halts for this ETF? What ordering, gap detection, replay or reconciliation mechanism is supported after a disconnect? Subscription acknowledgement and websocket pongs prove transport, not missed-event coverage.
3. For paper `/v2/account/activities`, is there an authoritative publication watermark or documented maximum publication delay for fills, fees, deposits, withdrawals and cash journals? Does exhaustive pagination prove completeness through an `until` timestamp, or only exhaustion of currently published results? How are delayed entries and corrections surfaced?
4. How can account balances/positions and activity history be reconciled to one authoritative as-of boundary? Is a server-side account snapshot timestamp or coherent snapshot/activity contract available? Equal values in successive reads do not by themselves establish a common timestamp.
5. A paper funding journal has `activity_type=JNLC`, executed USD status, a date-only effective field and a separate `created_at` timestamp. What is the effective cash/equity timestamp, and is `created_at` authoritative for that purpose? How can an owner verify whether the entry is already included in an intraday opening baseline without counting it twice?

Please distinguish Trading API paper-account capabilities from Broker API partner-only endpoints and identify any entitlement requirement. Keep this request within the current Alpaca-only ETF scope. Any new feed, paid subscription or policy exception would need a separate decision.

References reviewed: [account activities](https://docs.alpaca.markets/us/docs/account-activities), [stock status stream](https://docs.alpaca.markets/us/docs/real-time-stock-pricing-data). The reviewed documentation specifies activity types/pagination and status schemas; the guarantees asked for above were not established by those pages. That is a limitation of the evidence reviewed, not a claim that Alpaca cannot provide them.

October 7 public-documentation follow-up: the reviewed [Trading API websocket documentation](https://docs.alpaca.markets/us/docs/websocket-streaming) does not establish the required disconnect replay/completeness contract. The similarly named [Retrieve Account Activities reference](https://docs.alpaca.markets/us/reference/getaccountactivities) explicitly targets Broker API `/v1/accounts/activities`; its creation-date filter description is not evidence of Trading API paper semantics or of the journal's economic effective time. All five questions remain open. No launch gate or readiness percentage was promoted.
