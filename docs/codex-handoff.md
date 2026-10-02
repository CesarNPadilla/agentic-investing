# Codex handoff: Agentic Investing

## Latest: v0.8 controlled exploratory experiments (2026-10-01)

Read [human review 008](human-review-008.md), [historical evidence review 008](historical-evidence-review-008.md), and the [final machine-readable registry](examples/exploratory-retrospective-v08/final/registry.json). H01 reduced 2025 re-entries 55→49 and turnover 12.54×→11.35× but return also fell +1.03%→+0.45%; no winner is selected. H03 attributes low exposure primarily to sparse eligibility and records Risk Engine `NOT_EXERCISED`. H04's fixed no-cost/baseline/stressed returns were +1.7877%/+1.0262%/+0.2712%. $1,000 feasibility reduced whole-share skips 230→142 versus preserved $160 while concentration remained high. Final full results are immutable under local `AppData/Local/AgenticInvesting/exploratory-retrospective-v08/runs/controlled-v08-final/`; preliminary outputs were retained and superseded for audit-field completeness. H02 is `DEFERRED_NOT_IMPLEMENTED_NOT_RUN`. Both original v1.0.0 definitions, qualifying gates, Risk Engine and current $160 policy cap are unchanged; $1,000 is simulation only. 2025 is research-informed, 2026 OOS sealed, historical qualification BLOCKED, both strategies NOT_ELIGIBLE, forward paper 0/60, paper/production execution DISABLED. Stop after v0.8 for human review; do not release v1.1.0 or start v0.9.

## Latest: v0.7 design and preregistration (2026-10-01)

Read [human review 007](human-review-007.md), [preregistration](strategy-experiment-preregistration-v07.md), [swing candidate drafts](swing-candidate-design-v07.md), and [ADR-024](adr-024.md). H01–H04 and the v0.8 comparison protocol are recorded, but no candidate was implemented or backtested. The 2025 exploratory period is research-informed and cannot be a fresh holdout. The $1,000 feasibility plan is unchanged and NOT_RUN; $1,000 remains proposed, not deposited or policy-approved. Frozen v1.0.0 definitions, qualification gates, $100,000 research capital, current $160 policy cap, and completed $160 results remain intact. Long-term stays insufficient-data. 2026 OOS sealed; historical qualification BLOCKED; both strategies NOT_ELIGIBLE; forward paper 0/60; paper/production execution DISABLED. Stop for human review before v0.8 or any strategy version.

## Proposed $1,000 experimental-capital planning update

The latest human proposal is a future **$1,000** experimental-capital limit. It is not approved policy, a confirmed deposit, or authorization to trade. Keep the real portfolio separate and normalized research capital at **$100,000**. Preserve the completed $160 results and current $160 policy cap unless separately approved and changed. The [next-phase $1,000 feasibility plan](examples/exploratory-retrospective-v07/capital-feasibility-plan.json) is preregistered but **NOT_RUN**; it fixes whole-share affordability, skipped/rejected orders, concentration, utilization, turnover, costs, and drawdown without parameter optimization. Frozen strategy definitions and qualifying gates remain unchanged. The 2026 OOS is sealed, paper/production execution disabled, forward paper 0/60, and all actual investment activity remains subject to human approval and Risk Engine controls.

## Latest: v0.6 exploratory retrospective sandbox (2026-10-01)

Read [review 006](historical-evidence-review-006.md), the [sandbox runbook](exploratory-research-sandbox.md), [swing analysis](exploratory-swing-analysis-v1.md), and [long-term readiness](exploratory-long-term-readiness-v1.md). The immutable full v0.6 result is under local `AppData/Local/AgenticInvesting/exploratory-retrospective-v06/runs/exploratory-retrospective-v06-swing-v1-locked/`; repository examples contain the manifest and compact summary. Current-vintage 2025 swing normalized return was +1.03% against a nonqualifying VOO adjusted-all proxy +18.20%, with 127 sides, 55 re-entries and 12.54× turnover. The $160 feasibility replay is separate. Long-term had no run. Both v1.0.0 definitions are unchanged; 2026 OOS is sealed; qualifying historical validation blocked; both strategies NOT_ELIGIBLE; forward paper 0/60; paper/production execution disabled. Stop after v0.6 for human review; do not implement v1.1.0 or optimize yet.

## Latest: Historical Evidence Qualification v0.5 (2026-10-01)

Read [review 005](historical-evidence-review-005.md),
[provider qualification](data-provider-qualification-corporate-actions.md),
[ledger design](corporate-action-ledger-design.md), and
[VOO benchmark status](voo-benchmark-qualification.md). A read-only bounded
Alpaca snapshot through 2025-12-31 yielded 93 supported split/dividend rows
and one unattributed cash merger. The provider-neutral ledger preserves source
identity, immutable versions, corrections, separate knowledge/economic states,
and deterministic split/dividend calculations. One sampled NVDA split fully
matched independent terms; three sampled dividends were partial. Complete
event coverage, public timestamps, and VOO distribution amounts remain
unqualified. No strategy performance was recalculated or version changed.
Raw and qualification snapshots are outside the repo at
`C:\Users\cesar\AppData\Local\AgenticInvesting\corporate-actions-v05`.
2026 OOS is sealed, paper remains 0/60 and NOT_ELIGIBLE, and broker execution
remains disabled. Stop for human review; do not proceed to v0.6 automatically.
Verification: 500 tests passed; Ruff passed. One existing Starlette/httpx
deprecation warning remains.

## Latest: Strategy Experiment Lab v0.1 (2026-09-30)

This section supersedes earlier latest-work/next-task notes. Read [ADR-019](adr-019.md),
[gap analysis](experiment-lab-gap-analysis.md), [runbook](experiment-lab-runbook.md),
[human review](strategy-experiment-review.md) and [completion](experiment-lab-completion.md).

Implemented exactly two baseline research hypotheses, both immutable BACKTEST v1.0.0:
LONG_TERM_QUALITY_GROWTH (monthly, 5–10+ years) and SWING_TREND_MOMENTUM (daily).
Research -> Thesis -> Opportunity -> Strategy -> Backtest -> Validation -> Human Review
-> Future Paper Eligibility. Neither is a recommendation, paper approval or live permission.

`strategies/experiment_models.py`, `experiments.py` and `dispatch.py` add typed separate
dimension gates and the SMA200/SMA50, RSI14 50–75, prior-volume20, ATR14 swing baseline.
Research service, backtester and independent replay share dispatch and existing sizing,
proposal, indicator and Risk Engine logic. Absent experiment/diagnostic fields are omitted
from serialized legacy models to preserve old version bindings. No InvestmentPolicy
default, Risk Engine rule, execution endpoint or broker adapter was relaxed.

`experiment_lab/` freezes complete multi-period plans and registers strategy versions
before evaluation. A serialized database reservation records exposures before runs.
Overlapping OOS security/benchmark dates cannot be renamed into unseen data; failures
retain exposure. The two baselines share a preregistered cohort; completed replays return
cached evidence, never new unseen claims. Only three fixed development-only swing probes
are permitted (SMA50->55, RSI lower50->52, ATR2->2.2), with separate immutable versions.
No optimizer, automatic ranking or best-version selection exists.

The fixed synthetic study has 220 warm-up weekday observations and three six-session
periods: development 2020-11-05..12, validation 2020-11-13..20, OOS 2020-11-23..30.
These are generated fixtures, not real historical market regimes. Both capital modes
(research USD 100,000; experimental USD 160) retain the USD 160 policy sleeve ceiling.
Fractional simulation is requested in the smaller mode but remains BLOCKED_BY_POLICY.
Both hypotheses have UNSET mandatory controls and no qualifying entries. All 15 runs
reproduce exactly; both final reports are FAIL / NOT_ELIGIBLE. Zero fills/cash-only
performance does not validate investment behavior. RSI sensitivity changed gate counts;
no probe changed performance, and execution robustness remains unmeasurable.

Artifacts: `docs/examples/strategy-experiment-lab-v01/{plan.json,results.json,human-review.md}`;
concise human review in `docs/strategy-experiment-review.md`. Full datasets/runs persist
in the synthetic-only external registry at
`C:/Users/cesar/.codex/artifacts/strategy-experiment-lab-v01/synthetic.sqlite`.
Do not confuse that fixture database with actual holdings or deploy it as financial data.
Relevant source hash and data pins are recorded. Plan/source changes conflict with an
existing ID; preserve exposure receipts, never delete them to simulate unseen holdout.

Mandatory lab gates add exact replay equality, preregistered OOS and required strategy/
risk controls to existing StrategyValidationReport; human_review_required is always true.
Benchmark maximum drawdown is now included. No live eligibility status exists, and
historical/OOS/synthetic sessions earn zero toward 60 sequential non-synthetic forward
paper sessions. The forward-validation requirement remains unsatisfied.

Verification: 462 tests passed, 0 failed (43 new); repository Ruff passed. One existing
Starlette/httpx deprecation warning remains. Synthetic fixtures and temporary/local test
SQLite only; no credentials, private records, actual broker calls, order submission,
cancellation/modification, optimization, deployment, scheduler activation or commit.

Remaining gates: validated PIT fundamentals/theses/calendar/actions/universe provenance;
owner-approved fundamental/health thresholds, valuation/fit/concentration/sizing and
authorization; daily/experimental loss/freshness/day-boundary and swing risk controls;
validation thresholds and optional risk-free inputs. Current buy-only/whole-share and
swing forward-evidence restrictions are preserved, not hidden simulation exceptions.
Registry exposure checks cover only retained local history; external research and human
prior knowledge cannot be certified. PostgreSQL migrations/restore/auth remain pending.

Next recommended task: provenance-validated historical import and explicit review of
the UNSET controls/simulation-policy conflicts. STOP for human review. Do not begin
forward paper trading or automated optimization automatically.

## Latest: Backtesting & Strategy Validation Engine v0.1 (2026-09-30)

This section supersedes earlier next-task/latest-work notes. Read [ADR-018](adr-018.md),
[gap analysis](backtesting-gap-analysis.md), [runbook](backtesting-runbook.md) and
[completion report](backtesting-completion.md). Implemented path:
Research -> Thesis -> Opportunity -> Strategy -> Backtest -> Validation -> Paper Eligibility.
STOP before paper orders. Production trading remains disabled.

`backtesting/` adds immutable config/data/result/report contracts, provider-neutral archives,
materialized cutoff-only views, shared strategy/risk replay, next-session ledger and cost
rechecks, portfolio/performance/risk analytics, comparison, holdout-fold service and atomic
SQL experiment registry. Current APIs, scheduler and broker adapters are unchanged.
The shared digest now supports date objects without changing datetime encoding.
Shared strategies/review have an explicit historical_replay option; later-authored versions
retain timestamps and retrospective-bias warnings. Current callers preserve default behavior.

Every generated proposal receives the existing deterministic risk/replay review and admitted
fills receive another actual-cost risk check. Human review defaults to SKIP. Internal assumed
approval must be explicit. No rejected/insufficient proposal fills. Buy limits stay binding.
Research capital is configurable synthetic cash; current policy still caps attributed
acquisitions at USD 160. Sell/fractional ledger mechanics confer no policy permission.
Swing remains blocked by its pre-existing forward-evidence gate; no historical evidence is
fabricated to clear it. These are documented functional limits, not hidden exemptions.

Raw execution prices and separately vintage adjusted indicator histories prevent double
counting actions. Splits/reverse splits and same-close cash dividends are handled; separate
dividend payment schedules, symbol changes, delistings and mergers fail closed. Missing
historical fundamentals/research, unverified calendars/provenance and survivorship risks
are explicit. No actual historical provider or historical thesis archive has been installed.

Run `python -m backtesting.demo`: five synthetic sessions, one internal fill, ending equity
162.8505 from 160, validation FAIL / NOT_ELIGIBLE. Software test only; no investment
conclusion. Backtests always contribute zero toward at least 60 sequential non-synthetic
forward sessions. No strategy qualifies for production, and no execution is available.

Experiment tables are additive local bootstrap, not production migration. Exact strategy
definitions and experiment IDs are immutable; full datasets/configuration/results/reports
persist atomically. Active private data belongs outside sync. PostgreSQL operational
validation and future API authorization remain pending.

Owner settings remain unresolved: attribution/baseline, daily/experimental loss ceilings,
freshness/day boundary, reviewed valuation/fit/sizing/concentration and authorization,
swing controls, drawdown/observation/trade/turnover/data-quality validation gates and
optional risk-free assumptions. No production thresholds are inferred from fixture values.

Next recommended task: validated historical provider/import with calendar/action/revision
provenance and archived thesis availability, then explicit policy review of the limitations.
Do not automatically begin paper trading, optimization or deployment. Stop for human review.

Verification: 419 tests passed, 0 failed (47 new); repository Ruff lint and all 14
changed/new Python formatting checks passed. Existing Starlette/httpx warning remains.
Synthetic fixtures/temporary SQLite only. No broker execution was invoked by the
backtesting engine; no real broker connection or paper/production order was made.
Existing legacy tests still exercise their own synthetic execution fixtures.

## Latest: Opportunity & Strategy Engine v0.1 (2026-09-30)

This section supersedes earlier latest-work and next-task notes below. Implemented ADR-017:
Research -> Thesis -> Opportunity -> separate Long-Term/Swing Strategy -> TradeProposal
-> deterministic Risk -> Human Review / Reject -> STOP. Production execution stays DISABLED.

Read [ADR-017](adr-017.md), [runbook](opportunity-strategy-runbook.md),
[gap analysis](opportunity-strategy-gap-analysis.md) and
[completion report](opportunity-strategy-completion.md) before continuing.

`strategies/` contains models, OpportunityEngine, separate concrete strategies, sizing,
independent replay/review, SQL storage and OpportunityStrategyService. Technical indicators
are in `technical/indicators.py`. Existing ResearchAssessment, thesis reviews, policy,
experimental accounting and deterministic risk are reused. Proposal fields are additive;
generic risk review alone cannot qualify opportunity-backed proposals.

Trusted internal entry point: OpportunityStrategyService(store).run with assessment, current
thesis, opening/current state, policy, immutable strategy version, kill switch, explicit
time/fees and optional swing history/validation. The thesis must contain the assessment's
matching review. No API, scheduler or broker capability is added. Strategy authorization,
valuation/fit and swing controls are reviewed local inputs; defaults remain fail-closed.

StrategyStore bootstraps additive version/evaluation tables. Each evaluation atomically stores
opportunity, analysis, proposal/review when present, full inputs, experimental accounting and
correlated timestamped audit events. Version registration is separate and immutable; duplicate
content is idempotent, changed content conflicts. Persistence failures propagate. These
bundles contain private input data and must remain outside public logs and synced active DBs.

Indicators use exact supplied session calendars, availability timestamps, adjusted OHLCV and
adjustment vintages. No future bars or future-known adjustments are used. Provider/calendar
trust remains adapter-attested. No universal score, automatic selling, rebalancing, broker
translation or production parameters. Long-term horizons remain 5-10+ years; swing is research
only. Existing USD 160 attributed experimental cap, loss gates and qualification remain intact.

Verification: 372 tests passed (61 new), 0 failed. Repository Ruff passed; all 12 changed/new
Python files pass formatting. Existing Starlette/httpx warning remains. Used the documented
external venv, synthetic fixtures and temporary SQLite. No credentials, private database or
SDK logs read; no broker connection/order action, deployment, scheduler activation or commit.

Remaining owner values: attribution/baseline, loss controls, risk freshness/timezone, reviewed
valuation/fit/sizing/concentration, strategy authorization and swing settings. Provider gaps:
validated fundamentals/news/references, fees/marks, coherent complete ledger, ETF look-through,
historical data/calendar vintages. PostgreSQL migrations/concurrency/restore and API scope
authorization remain pending. Recommend an offline point-in-time backtesting harness reusing
these exact strategies with simulated next-session fills/costs and leakage tests. Do not begin
that phase automatically; this task ends for human review.

Status date: 2026-09-29. Latest work: Long-Term Research Agent v0.1 (ADR-016),
building on approved Investment Policy v0.2 and Portfolio Intelligence (ADRs 013–015).

## Latest: Long-Term Research Agent v0.1

Implemented in `agents/long_term/`: models, provider interfaces/statement bridge, pure
assumption and portfolio analysis, valuation interface, SQL storage, and service. Existing
ResearchOrchestrator/API, broker adapters, risk controls and policy defaults are unchanged.
Read [ADR-016](adr-016.md), [gap analysis](long-term-research-gap-analysis.md),
[runbook](long-term-research-runbook.md), [schema](long-term-research.schema.json), and
[completion report](long-term-research-completion.md) before extending it.

`LongTermResearchAgent.run`, `daily_cycle`, `quarterly_review`, `compare` are trusted internal
Python entry points. `ResearchStore.initialize` bootstraps additive v1 assessment, head,
run and completed-event tables. Assessment/thesis-review/event/completed-audit persistence
is atomic with optimistic revision conflict detection. STARTED audits precede provider calls;
FAILED records sanitize exception details. Crash-abandoned STARTED runs need investigation.
Latest/history readers and existing thesis history provide dashboard foundations; no new
HTTP route or installed scheduler is introduced. Scope authorization must precede API exposure.

Universe = configured policy universe plus actual holdings from a persisted observation ID.
GOOG/GOOGL research is canonicalized without merging real holdings or thesis revisions.
ResearchPlan is reviewed local configuration, never news instructions. Metric assumptions
use explicit unit/basis/period; incompatible periods and unknown inputs fail closed.
Direction states are separate from old thesis lifecycle; no BUY/SELL decisions exist.
Current thesis text can be updated from the reviewed plan while retaining original owner
rationale, human notes and all revisions. Omitted plans reuse the last assessment's plan.

News relevance requests review only. Completed-event receipts avoid repeated full research
after restart. Daily cycles poll quotes/news and research new events, due reviews, changed
plans or missing baselines; incomplete assessments retry at configured intervals. Explicit
quarterly reviews refresh full inputs and retain metric/assumption changes. Cost basis is
context only. STRONGER is not BUY and WEAKER is not SELL. No broker capability is injected.

Default source/sample checks reject synthetic research evidence. Tests opt in explicitly.
No new live adapter is configured: missing providers yield insufficient data. Statement
bridge trust defaults false. Source reliability is adapter-attested; production provenance
still needs validation. Valuation has its own 7-day default publication freshness, distinct
from reported financial-period freshness. Defaults are research heuristics, never unset
risk-policy controls. ETF look-through and diversification effects remain unknown.

Verification: 311 tests passed, including 29 new long-term cases; repository Ruff lint and
new-file formatting passed. Existing Starlette/httpx warning remains. Synthetic fixtures,
temporary SQLite and local checks only. No credential file, private broker payload or log
was read; no broker/network/order action, deployment or commit was performed.

Recommended next research task: implement a provenance-validated SEC/IR adapter with tests
for amendments, fiscal periods, units and company KPIs, then supply reviewed company plans.
Other outstanding work: live news/reference inputs, authenticated scope-aware API exposure,
worker installation/leases, PostgreSQL migrations/concurrency/restore validation, and the
previous complete-ledger reconciliation task. Production trading stays disabled.

The sections below retain the earlier foundation history; their historical test counts and
recommended-next-task paragraphs are superseded by this latest section where applicable.

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

## Historical research diagnostic 001 (2026-09-30 local)

The synthetic strategy experiment remains a clearly labeled software fixture.
`experiment_lab/historical_data.py`, `alpaca_historical.py`, `historical_fetch.py`,
`historical_plan.py`, `historical_research.py`, and `historical_run.py` add a
provider-neutral historical input contract, read-only Alpaca acquisition, frozen
research-only candidate rules/gates, and staged development/validation/OOS runs.
This counterfactual ledger cannot submit proposals or broker orders and cannot
grant paper eligibility. The $160 whole-share sleeve remains separate from the
$100,000 normalized research case. Existing synthetic lab execution now orders
all development and sensitivity runs before validation and OOS.

Using credentials from the external `AgenticInvesting/alpaca.env` location, a
read-only Alpaca IEX daily history was acquired. No credential value was printed
or copied into the repository. The frozen 2023–2024 development and 2025
validation diagnostic failed its preregistered gates; 2026 OOS was not computed.
Swing generated retrospective candidate sides, but Alpaca's adjusted download
does not attest point-in-time adjustment vintages or complete corporate actions.
No historical fundamentals were supplied, so quality-growth remained cash.
See [review 001](historical-research-review-001.md) and
[the historical lab runbook](historical-research-lab.md). Raw data, frozen plan,
results, and registry reside outside the repository under the user's local
`AppData/Local/AgenticInvesting` directory. The initial $160 rows were retained
for audit and superseded by a labeled corrective replay after a sleeve-cap fix;
OOS stayed unopened.

Historical qualification, the separate Phase 5 gates, human review, and all 60
forward-paper sessions remain unmet. Paper and production execution remain
disabled. Latest verification: 469 tests passed and repository Ruff lint passed.

## Historical qualification review 002 (2026-09-30 local)

The external `FMP.env` credential loaded without exposing its value, but the
historical statement API returned HTTP 402. Do not promote the adapter to a
point-in-time source: accepted timestamps and historical revisions remain
unverified. `HistoricalKnowledgeBoundary` excludes uncertain observations;
separate provider contracts and raw Alpaca IEX bars now cover ten securities
and VOO through 2025-12-31 only. The raw snapshot and immutable qualification
audit are under the user's external `AppData/Local/AgenticInvesting` directory.
The audit says no new qualifying validation was run and 2026 OOS was not opened.
Do not load the prior 2022–2026 adjusted export for further studies; it contains
a current-vintage adjusted series and is ineligible as a clean holdout.

The existing 2025 swing ledger was diagnosed without changing v1.0.0: 63
round trips, 55 same-symbol re-entries, 31 trend exits, 23 holding-limit exits,
9 ATR stops. See [turnover diagnostic](swing-turnover-diagnostic-v1.md) and
[review 002](historical-research-review-002.md). FMP access/revision lineage,
corporate-action availability and a qualifying data export remain blocking.
The prior 2025 +1.03% swing result is retrospective and nonqualifying. Both
strategies remain NOT_ELIGIBLE, forward paper 0/60, paper/production disabled.

## SEC EDGAR qualification v0.3 (2026-10-01 local)

SEC is now the primary historical-fundamental candidate; FMP is optional.
`experiment_lab/sec_edgar_historical.py` joins submissions and companyfacts by
exact accession and preserves `/A` filings. It fetched a dev/validation-only
coverage summary for ten symbols through 2025-12-31. The adapter is read-only,
uses an injected declared User-Agent, and refuses 2026 requests. Today's
companyfacts aggregation cannot attest original fact vintages or exact public
availability, so all live statements remain UNCERTAIN at the knowledge
boundary. No strategy performance was rerun. Review [SEC qualification](data-provider-qualification-sec-edgar.md),
[reconstruction](historical-fundamental-reconstruction.md), and
[review 003](historical-research-review-003.md) before a new architecture
decision. OOS remains sealed, paper 0/60, execution disabled.
# v0.9 handoff (2026-10-01)

See [human review 009](human-review-009.md), [risk readiness](risk-engine-readiness-v09.md), and the [synthetic replay](examples/risk-diagnostics-v09/replay-verification.json). Stop for human review after v0.9. Do not edit original strategies, v0.6-v0.8 evidence, policy cap, or frozen gates. H02 remains deferred. 2026 OOS is sealed, paper clock 0/60, execution disabled.
