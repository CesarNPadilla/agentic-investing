# Roadmap and phase gates

## Risk-policy approval resolution v1.0.1 (2026-10-01)

The [owner decision package](human-review-0101.md) preserves the v1.0 proposal and creates 35 pending choices, including ten numerical limits, independent capital/funding/environment decisions, whole-account risk, operations, and v1.1 implementation authorization. No choice is approved, no v1.1 work has started, and no policy or execution path changed. Current cap $160; production daily-loss stop unset; historical qualification blocked; 2026 OOS sealed; paper 0/60 and execution disabled. Stop for human decisions.

## Risk policy specification v1.0 (2026-10-01)

The [approval-ready design](human-review-010.md) proposes a $1,000 attributed sleeve and explicit capital, loss, freshness, and approval controls. Every new value is unapproved and inactive; the current $160 cap and unset production daily-loss stop are unchanged. The [future v1.1 backlog](risk-control-implementation-backlog-v11.md) is not started. Historical qualification stays blocked, both strategies NOT_ELIGIBLE, 2026 OOS sealed, forward paper 0/60, and paper/production execution disabled. Stop for human approval.

## Controlled exploratory experiments v0.8 (2026-10-01)

Completed approved H01 re-entry-reset candidate, H03 diagnostic instrumentation, H04's three fixed cost scenarios, and separate simulated $1,000 whole-share feasibility. [Human review 008](human-review-008.md) reports adverse as well as favorable outcomes; no winner or v1.1.0 is selected. **H02 remains `DEFERRED_NOT_IMPLEMENTED_NOT_RUN`.** All results are `EXPLORATORY_RETROSPECTIVE`; the $1,000 case is `CAPITAL_FEASIBILITY_EXPLORATORY` and does not change the current $160 policy cap. The 2025 comparison is research-informed; 2026 OOS remains sealed. Both strategies NOT_ELIGIBLE, forward paper 0/60, paper/production DISABLED. Stop for human review before v0.9.

## Strategy design and controlled preregistration v0.7 (2026-10-01)

H01 re-entry reset, H02 holding-limit exit review, H03 exposure decomposition, and H04 fixed cost sensitivity are [preregistered](strategy-experiment-preregistration-v07.md) for human review. H01/H02 are separate draft candidate IDs, not strategy versions. The 2025 exploratory period is research-informed, not a fresh holdout. The [$1,000 feasibility plan](examples/exploratory-retrospective-v07/capital-feasibility-plan.json) remains NOT_RUN and proposed only; $100,000 normalized capital, the current $160 policy cap, and historical $160 results remain distinct. No candidate backtest, v1.1.0 implementation, OOS access, paper clock, or execution change occurred. See [human review 007](human-review-007.md); stop before v0.8 until human approval.

## Proposed experimental capital planning update (2026-10-01)

The human proposes **$1,000** as a future initial experimental-capital limit. This is a planning proposal, **not** an approved Investment Policy change, deposit confirmation, or trading authorization. The current $160 policy limit and Risk Engine controls continue to govern any actual investment activity until separately approved and changed. The existing investment portfolio stays separate. Normalized strategy-research capital remains **$100,000**; completed $160 exploratory evidence is retained unchanged.

For the next exploratory phase, [preregistered $1,000 feasibility plan](examples/exploratory-retrospective-v07/capital-feasibility-plan.json) fixes the unchanged swing v1.0.0 definition, 2023â€“24 development/2025 validation periods, current-vintage data and VOO proxy, whole-share execution assumptions, and measures for affordability, skipped/rejected orders, concentration, cash utilization, turnover, costs, and drawdown. **Status: NOT_RUN.** It cannot grant paper or production eligibility or justify tuning parameters for $1,000. The 2026 OOS stays sealed; paper and production execution remain disabled; forward paper remains 0/60.

## Exploratory retrospective sandbox v0.6 (2026-10-01)

Implemented a separate, nonpromotable `EXPLORATORY_RETROSPECTIVE` runner over 2023â€“24 development and 2025 validation only. The unchanged swing v1.0.0 produced counterfactual trade diagnostics; long-term v1.0.0 remains unready. Qualifying validation remains blocked. The 2026 OOS is sealed, both strategies NOT_ELIGIBLE, forward paper 0/60, and paper/production execution disabled. See [review 006](historical-evidence-review-006.md). Stop for human review before any v1.1.0 design, optimization, OOS release, or paper work.

## Historical evidence qualification v0.5 (2026-10-01)

Implemented a versioned, provider-neutral corporate-action ledger and bounded
raw-price adjustment diagnostics. Alpaca returned 93 supported split/dividend
events through 2025, but only one sampled split has fully corroborated terms;
historical publication and complete event coverage remain unproven. VOO total
return is not qualified. Both strategies remain NOT_ELIGIBLE and 2026 OOS is
sealed. See [review 005](historical-evidence-review-005.md). That review preceded the separately requested v0.6 exploratory phase; it did not authorize qualifying validation or paper execution.

## Strategy Experiment Lab v0.1 (2026-09-30)

Implemented LONG_TERM_QUALITY_GROWTH v1.0.0 and SWING_TREND_MOMENTUM v1.0.0,
visible eligibility/exit-review diagnostics, immutable preregistration, durable OOS
exposure protection and three predetermined development-only probes. All 15 synthetic
runs replay identically; both hypotheses are NOT_ELIGIBLE. See the
[human review](strategy-experiment-review.md), [runbook](experiment-lab-runbook.md)
and [completion report](experiment-lab-completion.md).

Next proposed task: a validated PIT historical market/fundamental/thesis import with
calendar/action/revision provenance, plus explicit owner review of UNSET controls and
simulation-policy restrictions. No real historical investment validation, optimization,
forward-paper session, broker order or production enablement is claimed. Stop for review.

## Backtesting & Strategy Validation Engine v0.1 (2026-09-30)

Implemented an offline shared-strategy harness with point-in-time views, raw-price
next-session fills, independent risk review/rechecks, corporate-action ledger, metrics,
immutable experiments, explicit holdout folds and paper-eligibility reports. See
[completion report](backtesting-completion.md) and [runbook](backtesting-runbook.md).
Current whole-share/buy-only/USD 160 sleeve and swing forward-evidence policy remain
enforced, limiting experiments accordingly. No paper/live broker orders or optimization.
Next proposed work: provenance-validated historical data and action/calendar vintages,
plus owner review of the documented policy constraints. Stop for human review first.

## Opportunity & Strategy Engine v0.1 completed (2026-09-30)

Persistent opportunities now bridge structured research/theses to separate versioned
long-term and experimental swing strategies, deterministic indicators, bounded proposals
and independent risk/human review. Production execution remains disabled. See
[completion report](opportunity-strategy-completion.md) and [runbook](opportunity-strategy-runbook.md).
The offline backtesting task is now implemented above. Historical provider and
policy/qualification gaps remain; no strategy has qualified for forward paper trading.

## Phase 1 - Research (current)

Completed foundation: local API, normalized quote and account models, provider boundary,
synthetic research workflow, structured persistent reports, deterministic data-quality
warnings, PostgreSQL container configuration, isolated development environment, tests.

Next milestones:
Alpaca IEX quotes and paginated daily close history are implemented, with 20/50-bar
moving averages, split-adjustment provenance, and explicit history-failure handling.
Fundamentals, news topic analysis, and dated catalyst tracking are implemented through
validated JSON evidence input, with provenance, deterministic calculations, persistence,
and missing/stale/future-data handling. Live fundamentals/news adapters remain pending.
Daily session completeness and dividend adjustments remain pending.

Technical indicators now include Wilder RSI14, MACD 12/26/9, Bollinger Bands20,
20-interval returns/annualized volatility, and observed-history drawdown. JSON equity
portfolio imports calculate cash, long/short, gross/net, and symbol/sector/account
exposure. Versioned deterministic risk findings and evidence-linked research
assessments are persisted with Markdown export. See [workflow](research-workflow.md).

1. Choose and evaluate a licensed market-data provider; preserve timestamp, source,
   corporate-action handling, rate limits, retries, and data-quality status.
2. Extend existing price/technical/fundamental/news analysis with live evidence adapters.
3. Extend implemented JSON equity portfolio imports with reconciliation and FX support.
4. Evaluate bounded LLM synthesis beyond the implemented deterministic research assessment;
   preserve evidence validation and external-text isolation tests.
5. Add database migrations, durable workers/scheduling, and run/failure audit records.
6. Validate Docker/PostgreSQL startup, persistence, backup/restore, and access controls.

Exit gate: useful source-grounded reports, missing/stale-data handling, reproducible
calculations, automated tests, and a reviewed deployment boundary. No trading.

## Phase 2 - Portfolio intelligence

Long-Term Research Agent v0.1 (ADR-016) adds persistent evidence-linked assessments,
reviewed KPI assumption evaluation, separate thesis direction/lifecycle, multi-method
reported valuation, observation-linked portfolio context, and targeted daily/quarterly
research with durable run audits and event receipts. It exposes internal latest/history
and unranked Mag7 comparison interfaces. No broker or strategy capability is added.
Next research task: a provenance-validated SEC/IR fundamental adapter with amendment,
period/unit and company-KPI tests, followed by reviewed company research plans. Live news,
reference coverage, authenticated API exposure and operational worker/migration work remain.
See [research runbook](long-term-research-runbook.md).

Incremental foundation review (ADR-015): startup JSON policy configuration, evidence-preserving
analysis updates and authenticated thesis revision history are implemented. See the
[current gap analysis](phase2-policy-gap-analysis.md). Next: a provenance-preserving complete
ledger import/reconciliation workflow, with synthetic settlement/corporate-action tests and
no order actions. Database migrations/restore validation remain an operational gate.

Investment Policy v0.2 (ADR-014) adds monitoring-only sleeves, the approved position registry,
UNKNOWN original theses, persistent material events/review history and quarterly strategic
review requests. News can only request thesis review. Separate long-term/swing strategy
interfaces feed structured proposals into independent risk/human review; no new strategy
signals or execution are implemented. Swing controls remain UNSET until explicitly defined.
Timestamped analytics include Mag7, themes, speculative/swing exposure, verified correlations
and flow-adjusted VOO comparison when reliable evidence is supplied. Missing evidence remains
explicit. Required forward validation still includes 60 sequential non-synthetic sessions;
passing it cannot authorize production execution. See [ADR-014](adr-014.md).

ADR-013 separates real holdings, research universe and new-purchase permission. USD 160
now caps only explicitly attributed agent experimental capital, never existing portfolio
value. Authenticated Webull reads provide holdings/cash/open orders/cash activities;
persisted observations expose non-atomic and incomplete share/settlement-ledger evidence.
Whole-portfolio metrics, sourced classifications, informational concentration warnings and
revisioned position theses are implemented. Full broker share/settlement/corporate-action
coverage and reviewed experimental attribution remain gates. No auto-liquidation/rebalance.

Investment Policy + Portfolio Intelligence now provides an offline configurable policy,
complete-state import/reconciliation contract, account-wide metrics, deterministic hypothetical
risk evaluation and local durable evidence. Initial daily loss, freshness tolerance and day
boundary remain null and fail closed. No broker execution or strategy signals are added.
See [implementation and remaining decisions](investment-policy-portfolio.md). Read mappings
and pagination are implemented; coherent complete ledger evidence and production-grade
persistence/operations remain pending.

Persist accounts, positions, transactions, theses, purchase rationales, catalysts, target
allocations, risk assumptions, invalidation conditions, reviews, and performance history.
Gate: reconciled imports, reliable provenance, migrations, backups, and access controls.

## Phase 3 - Backtesting and paper trading

Implemented: versioned buy-and-hold/SMA strategies, validated historical inputs,
next-observation execution with fees/slippage, persisted local paper sessions,
benchmark/return/drawdown/trade/volatility/Sharpe metrics, and decision reasoning.
See [usage, conventions, limitations, and evaluation gate](backtesting-paper-trading.md).
Forward paper validation and provider-connected paper execution remain pending.

Historical qualification review 002: raw Alpaca development/validation bars and
provider-neutral adapters are in place, but FMP statement entitlement returned
HTTP 402 and corporate-action creation vintages remain unproven. No qualifying
validation or 2026 OOS run was performed. The next research milestone requires
entitled, revision-auditable filing data and action vintages, then a frozen
development/validation run. The paper clock stays 0/60 and execution disabled.
See [historical review 002](historical-research-review-002.md).

Historical qualification v0.3 adds tested SEC accession-level reconstruction.
The next evidence requirement is original archive-level XBRL verification and
a defensible public-availability convention, followed by corporate-action
vintage qualification. No strategy validation or OOS phase opens yet. See
[review 003](historical-research-review-003.md).

Version strategies and datasets. Measure return, benchmark, drawdown, win/loss, volatility,
risk-adjusted performance, and agent decisions. Control look-ahead and survivorship bias.
Gate: predefined acceptance criteria and demonstrated paper behavior. No live execution.

## Phase 4 - Human-approved trading

Phase v0.9 adds isolated synthetic risk diagnostics and a control inventory; see
[human review 009](human-review-009.md). The authorized experimental cap is still $160;
$1,000 remains an unapproved planning scenario. Daily-loss and other hard maxima
remain undefined. Qualifying validation is blocked, 2026 OOS sealed, forward paper
0/60, and paper/production execution disabled.

Agent -> trade proposal -> deterministic risk engine -> human approval -> broker adapter.
Implemented locally with a durable synthetic broker: immutable expiring proposals,
digest-bound approval, separate agent/human credentials, deterministic risk rechecks,
transactional idempotent execution, persistent kill switch, audit events, and ledger
reconciliation. See [Phase 4 workflow](human-approved-trading.md).
Production read-only account access is available through the separately authenticated API.
Live order integration and the production gate below remain pending.
Gate: broker/security review, isolated secrets, immutable approval details, audit logging,
idempotency, reconciliation, and kill switch tested end to end.

## Phase 5 - Limited automation

Implemented: human-registered, pre-evaluation strategy policies and a fail-closed
qualification check against persisted backtest and forward paper evidence. The default
gate requires backtest excess return >= 5%, maximum drawdown <= 15%, and Sharpe >= 0.8;
paper requires at least 60 sequential non-synthetic sessions, nonnegative return, and
maximum drawdown <= 10%. Evidence must be fully adjusted, match the registered strategy
and symbol, and paper observations must follow both policy registration and backtesting.
Policy caps cannot exceed USD 1,000 per order, USD 2,500 per position, USD 5,000 total
exposure, or USD 100 daily loss. Allowed symbols are restricted to AAPL/MSFT/SPY.

Automated order submission remains disabled: no execution endpoint or live execution
adapter exists, and no strategy currently has qualifying forward paper evidence. Market
hours, marked portfolio exposure, and daily-loss enforcement must be connected to a
trusted market-data and execution boundary before this gate can authorize automation.
See [Phase 5 readiness and limitations](human-approved-trading.md#phase-5-readiness-gate).

## Risk policy reconciliation v1.0.2

[Owner review 0102](human-review-0102.md) records N01â€“N10 numerical design approvals with original semantics and auditable user-message provenance. All 25 remaining decisions, including separate CAP-A, funding, environment use and AUTH-V11, remain pending. Next: explicit owner choices for whole-account loss, portfolio exposure, trusted sources, operational ownership and exceptions. Current executable cap remains $160; controls inactive; v1.1 not authorized or started; historical qualification blocked, 2026 OOS sealed, forward paper 0/60 and paper/production execution disabled.

## Risk policy approval reconciliation v1.0.3

[Owner review 0103](human-review-0103.md) records all 35 responses as APPROVE_AS_PROPOSED. CAP-A design and AUTH-V11 conditional implementation proposal are approved; concrete account loss/exposure limits, named sources/roles, funding evidence and environment selection still need completion. v1.1 remains unstarted; activation and paper/live permissions remain absent; executable cap stays $160.

## Owner-requested capital cap change

[Policy revision 0.3](capital-cap-change-v03.md) configures $1,000 for local research startup, retaining revision 0.2 historical defaults. Production funding is planned, not confirmed. Production deployment/execution and remaining v1.1 risk implementation remain blocked by missing inputs and qualification.
