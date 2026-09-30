# Long-Term Research Agent v0.1 completion report

Date: 2026-09-29. Backend research milestone; no live trading.

1. **Implementation:** Persistent ResearchAssessment, reviewed assumption evaluation,
   extensible KPIs, source-linked claims, freshness metadata, reported valuation methods,
   actual portfolio context, thesis revisions, targeted daily/quarterly workflows and audits.
   Original research reports and HTTP behavior remain compatible.
2. **Files created:** `agents/long_term/{__init__,models,providers,valuation,analysis,storage,service}.py`;
   `tests/test_long_term_research.py`; `docs/adr-016.md`;
   `docs/long-term-research-{gap-analysis,runbook,completion}.md`;
   `docs/long-term-research.schema.json`.
3. **Files modified:** `README.md`, `docs/architecture.md`, `docs/decisions.md`,
   `docs/roadmap.md`, `docs/research-workflow.md`, `docs/webull-automated-trading-runbook.md`,
   `docs/codex-handoff.md`, `docs/verification.md`. Existing application code is unchanged.
4. **Architecture:** ADR-016 isolates research from execution. Reviewed plans determine
   assumption checks; news creates review requests only. Research direction differs from
   position-thesis lifecycle and from portfolio sizing risk. Optimistic transactions retain
   atomic assessment/thesis/audit/event changes. Internal service interfaces avoid exposing
   private portfolio research through the existing unauthenticated research endpoint.
5. **Model/schema:** `long-term-research-v1`, with all requested assessment fields, plus
   scope/run IDs, raw evidence, metric periods/units, assumption results, reviewed plan,
   prior-assessment link, review kind and literal-false execution flag. Source/Claim models
   distinguish evidence facts from interpretations; unknowns remain null/empty with gaps.
   See [schema](long-term-research.schema.json).
6. **Providers:** Reused MarketDataProvider and NewsProvider; added FundamentalDataProvider,
   ReferenceDataProvider and ValuationAnalyzer. StatementProviderAdapter reuses validated
   existing financial analysis with explicit source trust. No mandatory paid dependency.
7. **Tests:** 29 new cases cover universe/holdings, aliases, model persistence/restart,
   direction/invalidation/plan transitions, missing/stale/future/untrusted/sample evidence,
   source references, company KPIs, valuation freshness, incompatible periods, portfolio
   cost/concentration, news injection/relevance/deduplication, quarterly/retry workflows,
   original-thesis/history preservation, transaction conflict rollback and execution isolation.
8. **Results:** Full suite 311 passed. Repository Ruff lint passed. All eight new Python
   files passed formatting checks. Existing Starlette/httpx deprecation warning remains.
9. **Security/safety:** No broker, strategy, proposal, simulation or dynamic execution
   capability in the new package; tests guard that boundary. No production/order operation,
   live data-provider call, credential inspection, policy override, deployment or commit.
   Provider exception details are sanitized; publisher text is never executed or sent to an
   LLM. Source adapters remain trusted code, not a Python security sandbox.
10. **Provider gaps:** No live fundamental/KPI/news/reference adapter added. Candidate
    SEC/IR, licensed market/news and reference integrations and validation requirements are
    documented in the runbook. Missing analyst estimates, peers and historical valuations
    are explicitly insufficient data.
11. **Known limits:** Deterministic reviewed metric assumptions do not replace broad business
    judgment. Source reliability is attested upstream. News keyword relevance is coarse.
    Reported valuation is descriptive, not fair-value estimation. ETF look-through and
    counterfactual diversification remain unknown. Freshness defaults need company/calendar
    review. SQLite tests do not certify PostgreSQL operations or hostile adapter isolation.
12. **TODOs:** Operational migrations/restore/concurrency review; distributed scheduler and
    crash recovery; authenticated scope-aware research API; audit pagination and queue receipt
    visibility; reliable live adapters; reviewed company plans; prior ledger reconciliation.
13. **Recommended next task:** Provenance-preserving SEC/IR fundamentals adapter, tested for
    amended filings, fiscal periods, units and missing company KPIs, with no order capability.

The user requested a completion check after an interruption. That check caught three new
test-fixture errors, lint cleanup, and unfinished documentation. Those were resolved; further
valuation-freshness, period-alignment, retry and alias tests were added before final verification.
