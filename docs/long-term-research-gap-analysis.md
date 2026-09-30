# Long-Term Research Agent v0.1 gap analysis

Repository inspected before implementation on 2026-09-29. Initial tracked tree was clean.
Authoritative context: handoff, approved policy v0.2, ADRs 013–015, roadmap, research and
Webull runbooks, existing provider contracts, Portfolio Intelligence, theses and tests.

| Area | Existing foundation | v0.1 addition |
| --- | --- | --- |
| Research | ResearchOrchestrator, reports and deterministic financial analysis | Separate long-term service; existing HTTP reports unchanged |
| Providers | MarketDataProvider, FundamentalProvider, NewsProvider | Extensible FundamentalDataProvider, reference protocol, statement bridge |
| Theses | Owner rationale, classification, revision history, review requests | Evidence-linked direction states and reviewed assumption evaluation |
| Persistence | SQLAlchemy JSON records and revisioned theses | Atomic assessment/head, thesis review, completed event and audit transaction |
| Portfolio | Stored observations and whole-portfolio analytics | Observation-linked allocation, cost/P&L and concentration context |
| News | Topic matching and news_to_reviews | Targeted durable review consumption; no sentiment-to-trade path |
| Scheduling | Quarterly review-request helper | Callable daily/quarterly cycles, completed-event deduplication and retry cadence |
| Valuation | Missing from prior research assessment | Multiple independently reported methods; explicit insufficient-data result |
| Dashboard readiness | Thesis history HTTP endpoint | Internal assessment latest/history, run audit and unranked comparison interfaces |

Still external/operational: reliable live fundamentals, company KPIs, news and reference
adapters; source attestation; reviewed company research plans; worker installation and leases;
production migrations, PostgreSQL race/restore tests; authenticated research HTTP integration.
No mandatory paid provider, production order method, or strategy signal is added.
