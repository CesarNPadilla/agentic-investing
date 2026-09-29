# Phase 1 architecture

## Investment Policy + Portfolio Intelligence extension

Complete normalized opening/closing state -> portfolio reconciliation -> metrics ->
independent deterministic investment-policy evaluator -> structured audit/evidence store.
The evaluator has no broker or strategy dependency and no execution capability. The
read-only complete-state protocol is separate from existing limited broker reads.
See [policy/state contract and limitations](investment-policy-portfolio.md).

Authenticated Webull SDK reads -> normalized portfolio_holdings/cash/open orders/cash activities
-> persisted observation + reconciliation gaps -> whole-portfolio intelligence and local theses.
Research universe and new-purchase allowlist are separate policy fields. Reviewed experimental
attribution alone consumes the USD 160 agent capital limit. Reference data is explicitly sourced;
unknown classifications stay unknown. See [ADR-013](adr-013.md). No path here mutates broker orders.

## Research foundation

API -> ResearchOrchestrator -> MarketDataProvider -> validated Quote
                            -> optional JSON financial/news/history/portfolio evidence
                            -> deterministic metrics, topics, catalysts, equity exposure
                            -> versioned research risk rules and bounded assessment
                            -> structured ResearchReport -> ReportRepository

The composition root is api/main.py. Providers are constructor-injected; the research
service does not import broker implementations or database technology. SQLReportRepository
owns transaction-scoped sessions. Report JSON includes schema version and immutable IDs;
each run creates a new row. Sources and timestamps accompany quotes. PostgreSQL is the
intended system of record; SQLite is a development fallback only.

External news, web pages, social posts, and model outputs are untrusted evidence, never
configuration or executable instructions. Validated JSON evidence ingestion is enabled;
no URL fetching or LLM execution is enabled. Future synthesis must validate responses, preserve
evidence provenance, and operate without broker or arbitrary tool capabilities.

The optional future BrokerReader returns normalized domain objects. It is not wired into
research. A future execution service must independently implement deterministic risk checks,
human approval bound to exact order details, expiration, replay protection, auditing, and a
kill switch. Read-only research infrastructure must not gain execution credentials.

Research reports alone are not a complete audit ledger. Jobs, provider failures, model
versions, prompts, datasets, and user approvals need durable audit records in later milestones.
No deployment to a Home Lab or live brokerage environment is part of this foundation.

The optional request body is `ResearchEvidence`. Analyzers retain original evidence in
version 4 reports. Financial/news provider protocols support later live adapters; the
API currently accepts these inputs and portfolio snapshots only as JSON. Explicit JSON
history overrides market-provider history. `reports/synthesis.py` generates evidence-linked
observations without a model call. `risk/analysis.py` records heuristic findings and
JSON Pointer references. `GET /reports/{id}?format=markdown` renders stored reports,
escaping external text without refreshing evidence. See [input contract](research-evidence.md)
and [extended workflow](research-workflow.md).

Implementation references:
- https://fastapi.tiangolo.com/tutorial/testing/
- https://docs.sqlalchemy.org/en/20/orm/session_basics.html

## Investment Policy v0.2 boundary (ADR-014)

Research -> Thesis -> Strategy -> Proposal -> Risk -> Human Approval -> Broker.
News/LLM -> Broker is forbidden. The implemented v0.2 path ends with research risk review.
`portfolio.registry`, `portfolio.theses` and `portfolio.storage` retain owner classifications,
UNKNOWN original theses, revisions and review evidence. `news.thesis_review` creates review
requests only. `risk.proposals` and `risk.workflow` expose separate long-term/swing interfaces
without broker dependencies; deterministic checks always run, regardless of confidence.
`portfolio.intelligence` and `portfolio.performance` require explicit timestamped evidence.
Policy defaults live in the v4 schema; [ADR-014](adr-014.md) and the
[policy contract](investment-policy-portfolio.md) define monitoring ranges and remaining gates.

## Incremental foundation (ADR-015)

Application startup chooses one validated policy source: explicit file, injected model or
safe defaults. External content cannot configure policy. Local analysis merges only explicit
changes into prior evidence and persists a new derived observation. Authenticated, bounded
thesis-history reads expose retained revisions without broker access. Existing broker adapters,
reconciliation contracts and all execution boundaries remain unchanged.
