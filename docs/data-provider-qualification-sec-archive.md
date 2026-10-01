# Historical evidence qualification v0.4: SEC accession archives

**Result: accession-specific source corroboration passed for the sampled facts; historical strategy-data qualification remains blocked.** The read-only archive adapter retrieves each filing's SEC index, original inline-XBRL HTML, and the matching extracted XBRL instance. It stores their bytes and SHA-256 hashes in immutable accession directories outside the repository at `C:\Users\cesar\AppData\Local\AgenticInvesting\sec-accession-artifacts-v04`. The cross-check report there is `crosscheck-v04.json` (SHA-256 `2ff461d1bab142afb12fac57ae26fab6f376d1c53634144c1e81f1cb36e372f8`). These are **retrieval-time hashes**, not proof that archive bytes were identical at the historical decision time. The 2026 OOS period was not requested.

| Filing | Form | Exact-period USD facts extracted | Accession-matched Company Facts | Discrepancies |
| --- | --- | ---: | ---: | ---: |
| AAPL `0000320193-25-000079` | 10-K | 11 | 11 | 0 |
| TSLA `0001628280-25-003063` | 10-K | 10 | 10 | 0 |
| TSLA `0001104659-25-042659` | 10-K/A | 0 | 0 | 0 mapped facts to compare |
| NVDA `0001045810-25-000023` | 10-K | 11 | 11 | 0 |
| AMZN `0001018724-25-000004` | 10-K | 10 | 10 | 0 |

The 42 compared facts matched in value, taxonomy tag, annual context start, report end, and USD unit. This is a **five-accession sample**, not a complete issuer or time-series qualification. The TSLA amendment remains a separate accession and event. It has no fact under this map; a zero-row comparison is not evidence that it made no other corrections. The reconstruction selector makes the latest accepted amendment take precedence only after its modeled availability, and does not borrow original-filing values when the amendment lacks a mapped fact. The SEC archive may have post-acceptance corrections; their absence is not proven by a current retrieval.

The historical-availability convention is **SEC acceptance timestamp plus 48 elapsed hours**, in UTC. It is a conservative research modeling delay, **not proof of the exact public dissemination time**. A filing is unavailable before that boundary. An amendment is a distinct version with its own acceptance and delay. The current Company Facts aggregation remains marked `revision_proven=False`; the archive cross-check narrows current-vintage uncertainty for sampled accessions but does not attest historical dissemination or absence of later archive corrections. The [SEC FAQ](https://www.sec.gov/about/webmaster-frequently-asked-questions) says exact first-public availability is not available; the [EDGAR archive documentation](https://www.sec.gov/search-filings/edgar-search-assistance/accessing-edgar-data) describes accession archives, and the [EDGAR API documentation](https://www.sec.gov/search-filings/edgar-application-programming-interfaces) describes Company Facts aggregation.

The only metric-map extension is `PaymentsToAcquireProductiveAssets` as an alternative capital-expenditure tag. NVDA and AMZN original accession instances contain annual, entity-wide USD facts for it ($3.236 billion and $82.999 billion respectively), and those values match accession-scoped Company Facts. No unsupported custom tags or EBITDA substitutions were added. All other missing values remain missing.

Corporate actions have a [separate qualification path](corporate-action-reconstruction-qualification.md). Raw Alpaca bars are not an adjusted total-return series; historical split/dividend announcement and effective-time evidence, adjustment reconciliation, and VOO benchmark total-return consistency remain unproven. The corporate-action gate stays blocked independently of this SEC filing result. No strategy optimization, qualifying backtest, or OOS release occurred.
