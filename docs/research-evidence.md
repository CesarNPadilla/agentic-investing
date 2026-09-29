# Phase 1: news, catalysts, and fundamentals

`POST /research/{symbol}` accepts an optional JSON body containing `fundamentals`,
`news`, or both, plus optional history and portfolio sections documented in the
[extended workflow](research-workflow.md). Existing requests with no body remain supported. The API validates
the evidence, computes deterministic analysis, and persists both inputs and outputs
in the same report. New reports use schema version 4; versions 1, 2, and 3 remain readable.
No database table change is required because reports are stored as JSON payloads.

## Try the example

With the local API running, from the project directory:

```powershell
$body = Get-Content -Raw docs/examples/research-evidence.json
$report = Invoke-RestMethod -Method Post 'http://127.0.0.1:8000/research/AAPL' `
    -ContentType 'application/json' -Body $body
$report.fundamentals
$report.news
Invoke-RestMethod "http://127.0.0.1:8000/reports/$($report.id)"
```

The fixture is entirely synthetic, including financial figures and event dates.
It produces 20% revenue growth, 20% net margin, USD 20 million free cash flow,
a current ratio of 2, debt/equity of 0.5, and USD 30 million net debt when evaluated
after retrieval. Its news and catalyst results change as the evidence ages and events
pass. The fixture is not automatically included in ordinary research requests.
The default quote provider supports AAPL only; other symbols require a configured
market provider that supports them.

## Financial input contract

All monetary inputs must use **full currency units**, the same currency, accounting
basis, consolidation scope, and fiscal-period basis. Convert thousands/millions
before submitting. Decimal strings are recommended to preserve precision. Monetary
figures and computed Decimal values are serialized as JSON strings.

`current` is a financial statement with inclusive `period_start` and `period_end`,
timezone-aware `filed_at`, and an HTTP(S) `source_url`. Flow values cover that period;
balance-sheet values are measured at period end. Omit unavailable metrics or use null.
Capital expenditures are a nonnegative cash outflow magnitude. Debt means total
interest-bearing debt; cash should consistently include the chosen cash/equivalents scope.
`previous` is optional and must be the matching fiscal period one year earlier, with
duration within ten days and period ends 350–380 days apart. Overlapping periods are
rejected. These checks do not verify accounting consistency or restatements; the
importer must select comparable statements and the appropriate filing versions.

| Output | Calculation |
| --- | --- |
| `revenue_growth` | Current revenue / prior revenue - 1 |
| `net_margin` | Net income / revenue |
| `free_cash_flow` | Operating cash flow - capital expenditures |
| `current_ratio` | Current assets / current liabilities |
| `debt_to_equity` | Total debt / equity |
| `net_debt` | Total debt - cash |

Ratios are fractions, so `0.2` means 20%. Zero or negative denominators do not produce
ratios. Missing inputs produce null metrics and explicit `missing_metrics`, rather
than invented zeros. Negative earnings, equity, free cash flow, and net debt are allowed.
Future retrieval/filing timestamps suppress calculations. Periods older than 150 days
and retrievals older than seven days generate warnings; these are freshness heuristics,
not an exchange or filing calendar. No valuation multiples, TTM reconstruction,
currency conversion, fair-value estimates, or investment recommendations are computed.

## News and catalysts

Each article has an ID, headline, publisher, HTTP(S) URL, timezone-aware publication
time, and associated symbols. Every article must include the requested symbol and
fall within the explicit `window_start`–`retrieved_at` interval. Maximums are 200
articles and 100 catalysts per request. Duplicate IDs are rejected; duplicate URLs
(ignoring fragments) count once, retaining the newest record. This does not detect
syndication across different URLs or establish independent corroboration.

Keyword matches group headlines into earnings, regulatory, corporate-action, and
product topics. Topics reference article IDs; they are not sentiment or impact scores.
`recent_article_ids` covers the preceding seven days relative to report generation.
An empty, successfully supplied article list differs from absent news evidence.
Retrievals older than 24 hours and a lack of recent articles produce warnings.
Future retrieval timestamps suppress news analysis.

Catalysts are explicitly supplied event claims, never dates guessed from headlines.
Each has a title, category, timezone-aware event time, article `evidence_id`, and
`certainty` (`estimated` by default or `confirmed`). Certainty is the caller's claim,
not independent verification. References to missing articles are rejected. Events
at or after report generation appear in `news.upcoming_catalysts`, sorted by date
and deduplicated by title/date/category; past events remain in the stored evidence.
The existing top-level `catalysts` string list is populated for compatibility.
No upcoming events leaves catalysts marked missing; it does not prove that none exist.

## Boundaries

This implementation consumes caller-provided JSON. It does not fetch URLs, financial
statements, or news feeds. Source URLs and publisher names provide traceability, not
authentication. External text is stored as data and never passed to tools or an LLM.
Both evidence sections carry a source, retrieval timestamp, symbol, and sample flag.
Invalid payloads and symbol mismatches return 422 before report creation.

`FundamentalProvider` and `NewsProvider` protocols support future adapters through
constructor injection into `ResearchOrchestrator`. Supplied evidence takes priority
over an injected provider. Provider failures preserve available quote/history and
mark the affected section missing without exposing provider diagnostics. The default
API uses only the JSON input path for these sections.

Reports remain `partial`: valuation and a business-specific investment thesis are
still pending. Portfolio exposure and bounded supporting/counter observations are
implemented in the extended workflow. News and fundamentals are not combined
with quote prices for valuation, avoiding currency/date/sample mismatches.
