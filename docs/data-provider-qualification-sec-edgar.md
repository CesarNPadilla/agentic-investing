# SEC EDGAR historical fundamentals qualification v0.3

**Result: CONDITIONAL as an accession-level filing reconstruction source;
FAIL for qualifying point-in-time strategy validation.** SEC EDGAR is the
primary candidate. FMP is optional and was not consulted for this phase.

The `SecEdgarHistoricalFundamentalProvider` uses the SEC submissions history
and companyfacts XBRL APIs. A declared contact-bearing User-Agent is injected
at runtime. A symbol must have an explicitly pinned CIK; this current mapping
is not assumed to prove historical ticker identity. The adapter retrieves
archived submissions shards when the recent list does not cover the study
period. It accepts only 10-K, 10-Q and their `/A` amendments, and filters
period ends, filing dates, and acceptance instants at or before 2025-12-31.
No 2026 filing facts are emitted.

Each normalized USD fact must match **the same accession, form, filing date,
report end, duration, taxonomy tag, and unit**. Conflicting facts for an
accession/tag/period are omitted. Every retained metric records its XBRL tag,
unit, dates, accession, and fact digest; the statement records filing and
companyfacts source digests. A `/A` filing remains a separate version, with its
own acceptance time. It cannot overwrite the earlier accession before that
time. Tests cover this behavior and archived-shard recovery.

| Capability | Result | Evidence / limit |
| --- | --- | --- |
| SEC API access and accession metadata | PASS | All ten requested symbols responded; 112 symbol-level filings from 2023–2025 (101 unique accession records because GOOG and GOOGL share a CIK). |
| Filing acceptance timestamp | PASS as metadata | All 112 records had explicit UTC `acceptanceDateTime`. A fact from a later acceptance is NOT_YET_KNOWN at an earlier timestamp. |
| Accession-level XBRL provenance | PASS as current-source lineage | 111/112 records had at least one exact accession-matched USD fact; one TSLA amendment had none under the strict tag set. |
| Amendment handling | PASS in software; CONDITIONAL empirically | One TSLA `/A` was retained separately. It had no matching facts under the selected tags; this does not imply it made no other disclosures. |
| Original historical value vintage | FAIL | Today's companyfacts aggregation supplies accession labels but no saved response from the filing's original dissemination. Accession matching does not prove an extracted fact was never corrected within that accession. |
| Exact public availability | FAIL | The SEC says there is no timestamp for first availability on sec.gov and dissemination lag is not guaranteed. Acceptance is a necessary lower bound, not proven public availability. |
| Historical ticker/reference mapping | CONDITIONAL | CIKs are explicitly pinned for the diagnostic; no historically timestamped symbol-change ledger was qualified. |
| Qualifying knowledge boundary | FAIL | At 2025-12-31, all 112 reconstructed records classify UNCERTAIN because original value vintage/public availability is not proven. None entered a qualifying strategy run. |

Coverage by symbol, restricted to 2023–2025 report periods accepted by
2025-12-31:

| Symbol | Filings | Annual | Amendments | Revenue | Operating cash flow | Capital expenditure |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| AAPL | 11 | 3 | 0 | 11 | 5 | 5 |
| MSFT | 11 | 3 | 0 | 11 | 11 | 11 |
| NVDA | 12 | 3 | 0 | 12 | 6 | 0 |
| AMZN | 11 | 2 | 0 | 11 | 11 | 0 |
| GOOGL | 11 | 2 | 0 | 11 | 5 | 5 |
| GOOG | 11 | 2 | 0 | 11 | 5 | 5 |
| META | 11 | 2 | 0 | 11 | 5 | 5 |
| TSLA | 12 | 3 | 1 | 11 | 5 | 5 |
| PLTR | 11 | 2 | 0 | 11 | 5 | 5 |
| INTC | 11 | 2 | 0 | 11 | 5 | 5 |

The strict tag map is not a full taxonomy mapping. In particular, missing
capital expenditure for NVDA or AMZN means this reconstruction cannot claim
free cash flow for those periods; a zero would be fabricated. Quarter cash-flow
facts with year-to-date duration are excluded from the quarterly period field
rather than misreported as single-quarter values. No EBITDA or valuation
metric is inferred.

The read-only, development/validation-only coverage snapshot is stored outside
the repository at `C:\Users\cesar\AppData\Local\AgenticInvesting\sec-edgar-qualification-003-run.json`.
It contains counts and boundary states, not a 2026 OOS performance result.
It can be regenerated without overwriting this artifact using
`python -m experiment_lab.sec_qualify --output <new-external-path>` with a
contact-bearing `SEC_USER_AGENT` environment variable.

The SEC documents [submissions and companyfacts APIs](https://www.sec.gov/search-filings/edgar-application-programming-interfaces),
including their update schedule. Its [EDGAR timestamp and dissemination FAQ](https://www.sec.gov/about/webmaster-frequently-asked-questions)
states that acceptance and public availability differ, with no exact first-
availability timestamp. A next qualification step is to capture each original
accession filing's archived XBRL/iXBRL bytes, match extracted values to that
artifact, and establish a conservative availability policy before simulation.
Until that evidence exists, keep the boundary closed.
