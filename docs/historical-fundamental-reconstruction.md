# Historical fundamental reconstruction v0.3

The reconstruction path is `SecEdgarHistoricalFundamentalProvider` →
`HistoricalStatement` → `HistoricalKnowledgeBoundary` →
`reconstruct_quality_metrics`. Provider-specific SEC fields never enter the
strategy rules directly. FMP remains an optional secondary adapter.

The SEC adapter pins CIKs, reads company submissions (including relevant
archived shards), and joins USD XBRL companyfacts by exact accession, form,
filed date, reporting period and duration. The output retains source and fact
digests, XBRL taxonomy tags, filing and acceptance times, and amendment status.
Only direct disclosed values enter `normalized_values`; conflicting or absent
facts are omitted. This prevents current-vintage facts from a later accession
or amendment being substituted into an earlier filing record.

The metric layer can derive annual revenue and earnings growth from two known
annual periods; free cash flow from known operating cash flow less known
capital expenditure; gross, operating and net margins; current plus
noncurrent debt and net debt; and return on assets. Each operand must pass the
historical knowledge boundary. A later amendment supersedes its original
period only after the amendment itself is accepted and its value vintage is
proven. Tests use explicit synthetic accession fixtures to verify both sides
of that boundary. Live SEC companyfacts records remain `revision_proven=False`,
so the live v0.3 metric reconstruction returns no qualifying values.

The following remain `INSUFFICIENT_DATA` rather than estimates: a safe EBITDA
denominator for net-debt/EBITDA, contemporaneous shares and market price for
free-cash-flow yield, growth durability across enough comparable periods,
valuation context, thesis state, portfolio fit, and any issuer-specific tags
outside the strict map. Quarterly cash-flow year-to-date facts are not treated
as single-quarter flows. The historical ticker/CIK mapping also needs
publication-aware evidence before strategy use. Therefore
`LONG_TERM_QUALITY_GROWTH v1.0.0` is **not ready** for a legitimate historical
backtest and its existing research rules have not changed.

The SEC identifies filing acceptance separately from public dissemination;
it does not provide an exact first-publication timestamp. The current
companyfacts endpoint is a present-day aggregation even when its facts carry
old accessions. A future qualifying implementation needs accession-archive
byte verification, a documented conservative availability convention, and
amendment/correction lineage. See the [SEC provider qualification](data-provider-qualification-sec-edgar.md).

## v0.4 accession evidence

The [archive qualification](data-provider-qualification-sec-archive.md) adds original
inline-XBRL and matching extracted-instance hashes for five sample accessions.
Direct instance extraction and accession-level comparison found 42 matching
mapped facts and no discrepancies. The TSLA 10-K/A is kept as its own event;
its lack of mapped facts does not license carrying the original values forward.
`PaymentsToAcquireProductiveAssets` is now mapped as capital expenditure where
the original NVDA and AMZN filing instances support it. The 48-hour delay
after SEC acceptance is a modeled knowledge boundary, not an attested public
availability time. Historical correction lineage and independent corporate
action evidence remain unresolved, so live records stay unqualified.
