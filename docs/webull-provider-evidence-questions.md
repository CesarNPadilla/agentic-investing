# Webull retail sandbox evidence questions

Webull's OpenAPI support/API team supplies these technical answers. The owner submits this prepared request through authenticated support and shares the response for engineering review. This request has not been sent. Do not include API keys, signed requests, private account identifiers or raw SDK logs.

Suggested subject: Retail cash sandbox / SCHB controls trial: data, accounting and event contracts

Scope: a controls-only SCHB ETF sandbox trial, with actual account equity as the whole-account denominator and a separate USD 1,000 experimental sleeve ceiling. No live trading or policy exception is authorized.

1. For retail stock depths, what are the units and meaning of `quote_time`, and what entitlement guarantees current SCHB bid/ask data? How can a client establish authoritative current halt status at startup and after a disconnect? Instrument OC, snapshot RTH, fresh prices and a quiet stream alone are insufficient for our current policy.
2. For retail cash activities using `list_activities` and `pagination_key`, what establishes publication completeness, economic effective time, late entries and corrections? How can balance/position reads and activity history be reconciled to a coherent authoritative boundary, including New York calendar-midnight equity and external flows? Exhausted currently published pages alone do not establish these guarantees.
3. What is the supported subscription type for retail order events? The installed Python SDK 3.0.2 request builder sends 7, while the reviewed subscription page says 1. A cash sandbox probe using the installed SDK received an acknowledgement and heartbeat. Which order-event coverage does this establish?
4. What heartbeat cadence, sequence/gap detection, replay or complete order-history reconciliation is supported for retail sandbox after a disconnect? Please distinguish retail OpenAPI from Broker API partner interfaces and identify any relevant entitlement or sandbox limitations.

References reviewed: [stock depths](https://developer.webull.com/apis/docs/reference/quotes/), [cash activities](https://developer.webull.com/apis/docs/reference/trade-cash-activity-by-type/), [retail trade events](https://developer.webull.com/apis/docs/reference/custom/subscribe-trade-events/). These are unresolved guarantees in the evidence reviewed, not a claim that Webull cannot supply them. A provider response is technical evidence to evaluate; it does not activate trading or automatically approve a policy amendment.


October 12: the local disposable passkey/guardian ceremony is independently complete; it does not answer these provider questions. A [fresh public-documentation follow-up](webull-provider-evidence-followup-1012.md) leaves all four questions open. This request remains unsent. The next provider-evidence action is owner submission to authenticated Webull support and sharing its technical response. No credentials or account identifiers are needed in the request.
