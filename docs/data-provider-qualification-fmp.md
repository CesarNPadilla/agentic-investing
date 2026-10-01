# FMP historical fundamentals qualification, 2026-09-30

**Overall: FAIL for qualifying historical validation.** The external credential
loaded at runtime, but the FMP stable income-statement request for AAPL returned
HTTP 402. The adapter stopped before accessing balance-sheet or cash-flow data.
No provider fundamentals were persisted, and no strategy consumed FMP values.

| Capability | Finding | Evidence and implication |
| --- | --- | --- |
| External credential | PASS | `FMP_API_KEY` loaded from the external `FMP.env`; only a Boolean loading result was printed. |
| Historical statements entitlement | FAIL | Read-only `stable/income-statement` AAPL request returned HTTP 402; no records were available to inspect. |
| Fiscal period, filing, acceptance, currency and raw digest fields | CONDITIONAL (schema only) | The normalized record supports these fields and a deterministic payload digest. Live response contents were unavailable. |
| Publication timestamp usable at simulation time | FAIL | FMP examples contain `acceptedDate`, often without a timezone. The adapter does not infer a timezone; such records remain uncertain and are excluded. |
| Historical revision/restatement provenance | FAIL | Current-vintage FMP statements cannot establish which values the API showed at an earlier simulation date. No immutable version history or as-reported filing comparison was available under this credential. |
| Point-in-time strategy use | FAIL | An accepted time alone cannot prove a current-vintage value was unchanged since acceptance. The knowledge boundary requires both a dated acceptance and proven revision provenance. |

The provider-neutral `HistoricalFundamentalProvider` accepts a replacement
implementation. `FmpHistoricalFundamentalProvider` receives its credential by
injection, strips no future period into the returned records, retains raw row
digests rather than credentials, and reports sanitized HTTP errors. Its
`HistoricalStatement` records symbol, fiscal period/end, filing and accepted
times, retrieval time, source, digest, normalized values, currency, statement
type, and any amendment indicator. Values are *candidates*, never certified
point-in-time observations. The acceptance field must include an explicit
timezone to become an instant; an old fiscal date never substitutes for it.
The requested test for a later restatement retaining an earlier acceptance date
could not be run after HTTP 402. That risk remains unresolved, not disproved.

FMP documents ordinary and as-reported statement endpoints and describes
`acceptedDate` as the SEC receipt time. It does **not** demonstrate to this
project that ordinary historical values are immutable or provide a replayable
earlier API vintage. Its own docs say statement updates occur after filing;
this is not a version attestation. See [FMP statement API](https://site.financialmodelingprep.com/developer/docs),
[FMP cycle times](https://site.financialmodelingprep.com/developer/docs/cycle-times),
and [FMP parsing statements](https://site.financialmodelingprep.com/developer/docs/parsing-statements).

Requalification requires an entitled read-only response, a documented timezone
or independent timestamp mapping, and immutable filing-level versions or
repeatable historical snapshots proving the values used at each decision date.
Any amended filing must have its own known availability instant. Until then,
`LONG_TERM_QUALITY_GROWTH` fundamental gates remain `INSUFFICIENT_DATA`.

Alpaca `adjustment=raw` bars were separately acquired for development and
validation through 2025-12-31. They have timestamp, OHLCV, feed, adjustment
mode, retrieval time and source digest. The daily timestamp labels the bar; a
trading-calendar close is a separate input. Raw bars avoid silently importing
today's split/dividend adjustment vintage. Raw history alone does not solve
corporate-action and symbol-mapping history. Alpaca explicitly says its
corporate-action creation time has no guarantee and API availability may lag an
announcement; even a `created_at` field is thus marked unverified. See
[Alpaca raw bars](https://docs.alpaca.markets/us/reference/stockbarsingle-1) and
[Alpaca corporate actions](https://docs.alpaca.markets/us/reference/corporateactions-1).
