# Long-Term Research Agent v0.1 runbook

Research only. Do not connect an execution adapter, supply broker credentials, create a
TradeProposal, or run any production order script for this workflow.

## Local service setup

Use the existing external Python environment and keep private database files outside the
repository/OneDrive. `ResearchStore.initialize()` adds the v1 tables using the existing Base;
it is local bootstrap, not a reviewed production migration. Existing APIs remain unchanged.

```python
from datetime import UTC, datetime
from sqlalchemy import create_engine
from agents.long_term.service import LongTermResearchAgent
from agents.long_term.storage import ResearchStore
from risk.policy import InvestmentPolicy

# In-memory smoke check: no network, synthetic prices, broker or credentials.
engine = create_engine("sqlite://")
store = ResearchStore(engine)
store.initialize()
agent = LongTermResearchAgent(store=store, policy=InvestmentPolicy())
assessment = agent.run("NVDA", scope_id="local-research", now=datetime.now(UTC))
assert assessment.thesis_status == "INSUFFICIENT_DATA"
assert assessment.current_price is None
assert not assessment.execution_available
assert store.get(assessment.assessment_id) == assessment
engine.dispose()
```

For portfolio research, pass `observation_id` of an already persisted, authorized
PortfolioObservation. Use a stable `scope_id` across snapshots. The service reads local
storage; it never refreshes broker accounts. Initialize holding theses through the existing
PortfolioStore workflow before research if append-only thesis reviews are wanted. Missing
theses are flagged and are not invented by the agent.

The default policy researches Mag7 plus actual holdings in the observation, including the
14 owner holdings when present. Configure `InvestmentPolicy.research_universe` to monitor
additional securities without a snapshot. Do not infer ownership from that configuration.
GOOG maps to GOOGL for issuer research; actual portfolio share classes remain distinct.
The price in an issuer assessment belongs to its canonical symbol, not both share classes.

## Input contracts and provenance

Inject read-only market, fundamentals, news and reference providers by constructor. Omit any
unavailable provider. Provider exceptions are sanitized to `method:unavailable_or_invalid`;
symbol mismatches and malformed responses are not used. No fake fallback data is produced.

- Reuse `market_data.base.MarketDataProvider` and `news.analysis.NewsProvider`.
- `FundamentalDataProvider.get_fundamentals(symbol)` returns extensible named Metrics,
  sourced Claims and Sources. Units and quarter/annual/TTM/point/forward bases are explicit.
  Metric start/end periods must exactly match the source data period. Forward multiples
  use the observation period; the provider must explain forecast horizon in its claim.
- `StatementProviderAdapter` wraps existing FundamentalProvider. It reuses the current
  financial calculations and year-over-year validation. It requires explicit
  `trusted_source=True` after upstream source review; default source trust is false.
  It does not label YTD as quarterly or annual, or invent unavailable KPIs.
- `ReferenceDataProvider.get_reference(symbol)` returns the existing SecurityReference.
  Unverified/expired references are retained as evidence and flagged unavailable.
- `ValuationAnalyzer.analyze(metrics)` receives only eligible fresh metrics. The default
  ReportedValuation preserves P/E, forward P/E, price/sales, EV/revenue, EV/EBITDA, FCF yield,
  growth-adjusted values, historical ranges and peer medians when supplied. It performs no
  cross-period ratio construction, ranking or automatic cheap/expensive judgment.

Source records retain type, publication/retrieval times, period, affected symbol, claim,
URL, reliability, sample and historical flags. Prefer reviewed SEC/IR/earnings evidence,
then reliable market data and reputable news. Text remains untrusted data. Source flags
are not proof of authenticity; provider adapters must establish provenance. Typed claims
distinguish facts from interpretations and require resolvable source IDs.

ResearchAssessment schema: [JSON Schema](long-term-research.schema.json). Null means unknown;
empty narrative lists mean no supported claims, accompanied by named missing-data categories.
Raw input evidence is retained separately from eligible metrics. A future UI must escape
all provider text; no HTML/Markdown renderer is introduced here.

## Reviewed assumptions and thesis history

ResearchPlan is trusted local configuration with plan ID, symbol, reviewer/time, thesis
text and named assumptions (metric, unit, basis, comparator, threshold, optional explicit
invalidation). Do not derive this configuration from news/LLM instructions. No real-company
thresholds or ownership reasons are seeded. Supply company-specific metrics such as Azure
growth, Data Center growth, foundry customers, deliveries, cash burn, stablecoin economics,
or Bitcoin/power economics as independently sourced fields.

Same-basis assumptions must use matching periods; ambiguous/latest-period ties fail closed.
Changing the reviewed plan resets directional comparison. Omitted plans reuse the prior
assessment's plan. To revise one, supply a new reviewed version. Current thesis text is
updated from that plan; original thesis, human notes and old revisions are preserved.
Invalidated or archived lifecycle states are never automatically reactivated. Research
history records all six direction states without changing the old lifecycle schema.

Missing valuation and business context remain visible even when an available reviewed
assumption can be evaluated. Direction describes those assumptions, not a complete investment
recommendation. Portfolio concentration and historical cost/P&L are separate fields.

## Daily and quarterly operations

Call `agent.daily_cycle(scope_id=..., now=..., observation_id=..., plans=...)` from a trusted
host scheduler. No system scheduler is installed or activated by this change.

1. Refresh quotes and news for the configured universe.
2. Reuse news relevance analysis and persist thesis-review requests.
3. Research missing baselines, new material-topic events, due quarterly reviews, changed
   plans, overdue full reviews, or incomplete assessments eligible for retry.
4. Persist assessment, thesis history, completed-event receipts and audit atomically.
5. Otherwise persist a SKIPPED audit with quote/news poll evidence; no fundamentals fetch.

Defaults are configurable research heuristics: 24h market/news freshness, 7d source
retrieval freshness, 150d financial-period age, 7d valuation publication age, 24h incomplete
retry, 90d full-review fallback. They do not populate unset execution risk-policy controls.
Annual reporters or company-specific calendars may need a separately reviewed configuration.
`LATEST_REPORTED` means eligible supplied evidence, not proof no newer filing exists.

Earnings relevance and existing quarterly due requests select quarterly review. Explicit
`quarterly_review(symbol, ...)` forces a deeper provider refresh and records changes in
metrics, assumptions and thesis direction against the previous assessment. Guidance,
business KPIs, valuation, catalysts, risks, portfolio role and invalidation conditions are
retained where sourced; absent inputs stay unknown. No period values are silently blended.

Event receipts survive restart. A failure leaves the event eligible for retry; concurrent
assessment/thesis revision conflicts roll back together. Review requests themselves remain
an immutable queue; receipts identify those consumed by this research scope. Existing queue
HTTP endpoints do not yet expose completion receipts. STARTED runs left by crashes require
operator investigation; do not relabel them successful. Provider timeouts/retry policies
belong in adapters; no distributed scheduler lease exists yet.

## Internal read interfaces

`store.get(id)`, `store.latest(scope, symbol)`, `store.history(scope, symbol, limit=100)`
(newest first, maximum 500), `store.runs(scope, symbol)`, and existing
`store.portfolio.thesis_history(account, symbol, after_revision, limit)` support later APIs.
`agent.compare(scope_id=...)` returns canonical-symbol-ordered Mag7 records and explicit
missing assessments, with comparable growth/profitability/financial-health/cash/valuation/
competitive/AI/catalyst/risk/portfolio fields. It does not rank companies.

These are trusted internal Python interfaces. Before HTTP/dashboard exposure, add caller
authentication, scope/observation authorization, pagination for audits, rate limits and safe
text rendering. ETF look-through, correlations beyond existing evidence, and counterfactual
diversification impacts remain unknown.

## Provider gaps and candidates

No mandatory paid provider is added. Candidate integrations for subsequent evaluation:

| Gap | Candidate to evaluate | Required validation |
| --- | --- | --- |
| Filings and standardized statements | SEC filings/XBRL adapter | Source identity, amendments, fiscal periods, taxonomy/units, retrieval policy |
| Guidance and company KPIs | Company IR and official earnings releases | Reliable document provenance and company-specific extraction |
| Quotes and valuation inputs | Existing Alpaca adapter or another licensed provider | Coverage, consolidated-vs-IEX limitations, timestamp/entitlement checks |
| Material news | Official company feeds or licensed news provider | Symbol relevance, publication times, deduplication and usage rights |
| References/ETF holdings | Reviewed reference and fund holdings provider | Classification provenance, share classes and look-through dates |

These are candidate directions, not claims about current coverage, pricing or suitability.
No live adapter or new subscription was evaluated during this implementation. Analyst
consensus, forward estimates, historical valuation and peer sets need licensed/reliable
inputs before useful conclusions can be generated.

## Verification

Run `python -B -m pytest -q`, `python -B -m ruff check .`, and
`python -B -m ruff format --check agents/long_term tests/test_long_term_research.py`.
Tests use synthetic fixtures only and temporary SQLite storage. Test data is rejected by
the new agent by default; only tests explicitly enable `allow_test_data=True`.
