# Codex handoff: Agentic Investing

Status date: 2026-09-29. Current work: Investment Policy + Portfolio Intelligence,
including real existing portfolio / experimental capital separation (ADR-013).

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
  `research_universe`; independent `new_purchase_allowlist`. Research and purchase sets
  initially retain AAPL/MSFT/SPY, but holdings outside them are valid to analyze. VOO is
  a benchmark, not automatic purchase permission. Authenticated holdings can authorize
  research outside the configured universe; user-supplied evidence cannot grant permission.
- Owner policy v0.1 records long-term growth, VOO / S&P 500 benchmark, daily research,
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
- Policy/evaluator schemas are v3, state schema v2; new database tables are additive.
  Older evidence tables remain untouched and require their matching reader.
- `/trading/automation/status` remains fail-closed with `execution_available: false`.
  No scheduler, production execution adapter or automated-order route is added.

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

Read [ADR-013](adr-013.md), [policy/API/metrics contract](investment-policy-portfolio.md),
[roadmap](roadmap.md), [human-approved synthetic workflow](human-approved-trading.md) and
[Webull runbook](webull-automated-trading-runbook.md). Historical sandbox walkthroughs are
not authorization for this phase. Source/schema defaults are in `risk/policy.py` and
`docs/investment-policy.initial.json`; old policy names fail validation.

Run the complete pytest suite and Ruff. Focused coverage is in
`tests/test_portfolio_intelligence.py`, `tests/test_investment_policy.py`,
`tests/test_policy_v01.py` and `tests/test_broker_contract.py`. Tests use synthetic broker
fixtures only; never replace them with real credentials or private account payloads.
The workspace has an existing staged initial repository snapshot; do not discard or
commit unrelated user changes. Review staged artifacts separately before any publication.
