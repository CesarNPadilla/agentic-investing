# Codex handoff: Agentic Investing

Status date: 2026-09-29. Current work: Investment Policy + Portfolio Intelligence,
including approved Investment Policy v0.2 (ADR-014) and portfolio/capital separation (ADR-013).

## Safety boundary

Production trading, automated execution and automatic rebalancing remain disabled.
Do not submit, cancel or modify orders. No strategy-specific entry/exit signals are
implemented in this phase. Existing holdings must never be automatically liquidated.
Future live execution requires separate owner authorization, human approval and an
independent production review. A hypothetical risk pass is never execution authorization.
Never open, print, copy or request credential/token/account values, SDK caches, raw
production responses or private log contents in Codex chat. Keep active private data
outside the repository and OneDrive. No production broker calls were made for this work.

## Current implementation

- Research API and evidence reports remain available; Alpaca IEX market data is optional.
  Fundamentals/news live adapters and forward validation remain pending.
- Existing Phase 3 backtests/local paper simulation and Phase 4 synthetic execution are
  separate. The synthetic trading routes and broker-read routes remain disabled by default.
- Three scopes are explicit: all actual `portfolio_holdings`; configurable
  `research_universe`; independent `new_purchase_allowlist`. Research includes the Magnificent Seven plus actual holdings. Purchases independently
  retain AAPL/MSFT/SPY until explicitly changed; holdings outside remain valid to analyze. VOO is
  a benchmark, not automatic purchase permission. Authenticated holdings can authorize
  research outside the configured universe; user-supplied evidence cannot grant permission.
- Owner policy v0.2 records long-term growth, VOO / S&P 500 benchmark, daily research,
  weekly portfolio review, nonautomatic rule/event-driven rebalancing, required theses,
  mandatory audit/kill switch and future human approval.
- `agent_experimental_capital_limit = 160` replaces the earlier whole-portfolio USD 160
  cap. Only reviewed experimental quantities/cost basis and exact open order IDs count.
  Attribution is never inferred from symbol or account size. Missing attribution fails
  closed; an explicitly reviewed empty allocation can represent a not-yet-funded experiment.
- Whole-portfolio metrics include market value/cost/unrealized P&L, allocations, cash,
  top concentration, equity/ETF classification and direct sector/industry exposure from
  reliable references. >20%/>30% concentration warnings are informational only.
- Authenticated read endpoints normalize Webull positions/cost/market value, cash and
  settlement components, buying power, all open-order pages and cash activities. Snapshot
  reads persist observations and optional opening/closing reconciliation. New local metadata
  endpoints store reviewed attribution/reference data and revisioned position theses.
- Full share-ledger reconciliation remains unverified for Webull: cash activities omit
  share quantities and settlement deltas; separate reads are not atomic and marks lack
  market timestamps. Unknowns and gaps are explicit, so these reads cannot falsely pass
  strict reconciliation. The generic engine replays complete typed ledgers when supplied.
- Position theses contain ownership reason, original/current thesis, catalysts, risks,
  invalidation conditions, target allocation, last review and append-only agent reviews.
  Original thesis and old revisions are retained; concurrent edits fail with revision conflict.
- Policy/evaluator schemas are v4, state schema v2; new database tables are additive.
  Older evidence tables remain untouched and require their matching reader.
- `/trading/automation/status` remains fail-closed with `execution_available: false`.
  No scheduler, production execution adapter or automated-order route is added.

## v0.2 additions

- Monitoring sleeves: Core 30-45%, Strategic 40-55%, Satellite 10-20%. Unspecified position
  sleeve assignments remain UNASSIGNED; ranges do not trigger orders.
- The approved 14-symbol registry seeds actual observed holdings. Original theses remain
  UNKNOWN; current research theses, conviction, targets and catalysts are not invented.
- Expanded theses retain material events, review history, human notes and original rationale.
  News creates review requests only; quarterly strategic reviews are enqueued on demand.
- Separate long-term/swing interfaces emit digest-bound TradeProposals into independent risk
  review. Successful checks return REQUIRE_HUMAN_REVIEW, always execution_available false.
  Swing limits, stop rules and holding periods remain unset; 60-session evidence is required.
- Metrics add Mag7, market cap, speculative, crypto, themes and swing vs swing-eligible
  exposure. Correlations need verified references; VOO return/volatility/drawdown need aligned
  adjusted flow-aware history. Missing risk-free/annualization inputs remain null.
- Experimental capital records assigned cost, open commitments, realized/unrealized P/L
  and explicit strategy IDs. It never caps the existing portfolio value.
- New authenticated local routes persist news-review requests, review queues and proposal
  risk reviews. No route submits/cancels/modifies orders. Structured audits include reasons
  and digests; private stored records retain full evidence links.
- Architecture: Research -> Thesis -> Strategy -> Proposal -> Risk -> Human Approval -> Broker.
  Never News/LLM -> Broker. The implemented path stops at risk review.

## Required decisions and remaining work

1. Owner explicitly supplies experimental baseline/attribution. Do not treat the whole
   existing portfolio as experimental or infer lots based on AAPL/MSFT/SPY membership.
2. Experimental maximum loss, daily-loss limit, freshness tolerance and daily-loss timezone
   remain null. No substitute values are approved. Required missing controls reject proposals.
3. Owner supplies position theses, target allocations and strategy rules. Never invent
   ownership reasons, catalysts, sale decisions or entry/exit signals.
4. Corroborate complete broker share/settlement/corporate-action history and coherent
   timestamps; review partial fills/cancel acknowledgement, pagination/rate limits and
   full attribution lifecycle. Current Webull cash history is not full transaction evidence.
5. Establish a reliable reference-data provider, licensed adjusted market data and calendar
   handling. ETF look-through, FX and general derivative valuation remain unsupported.
6. Validate versioned database migrations, PostgreSQL concurrency, retention, access controls
   and backups. Local tests do not certify production deployment.
7. Future strategy qualification still requires the existing Phase 5 evidence gates:
   backtest excess return >= 5%, maximum drawdown <= 15%, Sharpe >= 0.8, and at least
   60 sequential non-synthetic forward-paper sessions with nonnegative return and drawdown
   <= 10%. No strategy currently qualifies. Do not enable order execution to address this.

## References and verification

Read [ADR-014](adr-014.md), [approved v0.2 policy](investment-policy-v0.2.md), [ADR-013](adr-013.md), [policy/API/metrics contract](investment-policy-portfolio.md),
[roadmap](roadmap.md), [human-approved synthetic workflow](human-approved-trading.md) and
[Webull runbook](webull-automated-trading-runbook.md). Historical sandbox walkthroughs are
not authorization for this phase. Source/schema defaults are in `risk/policy.py` and
`docs/investment-policy.initial.json`; old policy names fail validation.

Run the complete pytest suite and Ruff. Focused coverage is in
`tests/test_portfolio_intelligence.py`, `tests/test_investment_policy.py`,
`tests/test_policy_v01.py`, `tests/test_policy_v02.py` and `tests/test_broker_contract.py`. Tests use synthetic broker
fixtures only; never replace them with real credentials or private account payloads.
Preserve unrelated user changes. No commit, deployment or broker connection is required
to validate this phase. Review staged artifacts separately before any publication.

Latest verification: 282 tests passed; Ruff lint passed. Changed Python files pass formatting.
Repository-wide formatting has pre-existing differences outside this phase. All broker fixtures
are synthetic; no broker credentials were read and no broker connection or order action occurred.


## Latest incremental Phase 2 pass (ADR-015)

Inspected existing code, roadmap, architecture and v0.2 policy before editing. Most v0.2
foundation was already implemented; preserve it. The initial tree for this pass was clean.
[Gap analysis](phase2-policy-gap-analysis.md) distinguishes completed work from external-data,
operational and owner-decision gaps. No broker implementation was changed or connected.

Closed three practical gaps:

1. `AIL_INVESTMENT_POLICY_FILE` loads reviewed UTF-8 JSON at startup via `risk.policy`.
   Unset path retains safe defaults. Missing/invalid configured files stop startup with
   sanitized errors; file plus Python injection is rejected. No runtime policy mutation.
2. Analysis enrichment now preserves omitted experimental attribution, references,
   correlations and performance evidence. Explicit null/empty values clear them. Derived
   observations retain their parent ID; no existing observation is mutated. This is not
   automatic inheritance across fresh broker snapshots.
3. Authenticated thesis revision history is available at
   `/broker/accounts/{account_id}/theses/{symbol}/history`, ordered ascending, with
   `after_revision` (default 0) and `limit` (default 100, maximum 500). It reads only local
   storage and returns an empty list if no revisions match. Existing latest-thesis reads work.

Changed code: `api/config.py`, `api/main.py`, `api/broker.py`, `risk/policy.py`,
`portfolio/storage.py`. Added `tests/test_phase2_foundation.py` (9 cases). Updated the
architecture, roadmap, policy contract, Webull runbook and decisions; added ADR-015 and
phase2-policy-gap-analysis.md. No schema/table version change was needed.

Validation: full pytest suite 282 passed, including broker contracts and execution-safety
regressions; Ruff lint passed. One existing Starlette/httpx deprecation warning remains.
Tests use temporary databases and synthetic data. No .env/credentials or private broker data
were read for this task, and no order was submitted, canceled or modified.

Recommended next task: an authenticated complete-ledger import with source/provenance and
reconciliation against stored broker observations. First test synthetic settlement changes,
transfers, corporate actions and partial fills. Never infer missing share movements from
cash activities or clear the non-atomic broker flag without corroborating evidence.
Operational migrations and restore tests remain required before production data deployment.

Owner decisions are unchanged: explicit experimental baseline/attribution; daily and
experimental loss limits; freshness tolerance/day boundary; current theses and position
allocation targets; any purchase-list changes; swing controls. Daily/weekly scheduling,
review-request completion, reliable live references and actual forward validation are still
pending. No new investment decision or strategy signal was assumed in this pass.
