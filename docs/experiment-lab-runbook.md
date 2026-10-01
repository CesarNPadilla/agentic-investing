# Strategy Experiment Lab v0.1 runbook

The lab defines hypotheses and produces evidence for human review. It does not issue
investment recommendations, optimize parameters, submit orders or start forward paper trading.

The v0.6 [exploratory registry](examples/exploratory-retrospective-v06/registry.json) and [manifest](examples/exploratory-retrospective-v06/manifest.json) pin the unchanged v1.0.0 definitions and an independent `EXPLORATORY_RETROSPECTIVE` result digest. They do not alter the original synthetic lab registry or grant qualifying/paper status. See [classification](research-evidence-classification.md) and [review 006](historical-evidence-review-006.md).

Capital planning after v0.6 proposes a **$1,000** experimental amount for a separate future feasibility simulation, [preregistered here](examples/exploratory-retrospective-v07/capital-feasibility-plan.json). It has **not run** and is neither an approved policy limit nor a confirmed deposit. The $100,000 normalized research case and archived $160 results remain distinct; the existing $160 Investment Policy cap and Risk Engine controls are unchanged. No strategy parameter is to be tuned specifically for $1,000.

## Definitions

`experiment_lab.definitions.initial_definitions()` returns exactly:

| ID | Version | Domain | Status | Hypothesis |
| --- | --- | --- | --- | --- |
| LONG_TERM_QUALITY_GROWTH | 1.0.0 | LONG_TERM | BACKTEST | Infrequent 5–10+ year growth exposure backed by durable business/fundamental quality, health, thesis, valuation and fit |
| SWING_TREND_MOMENTUM | 1.0.0 | SWING | BACKTEST | An intentionally simple trend/momentum baseline worth evaluating, not a claim of profitability |

Internal domain values retain `long_term` / `swing` for interface compatibility.
Long-term research symbols: AAPL, MSFT, NVDA, AMZN, GOOGL, GOOG, META, TSLA, PLTR, INTC.
Swing excludes GOOG from that list. GOOG/GOOGL are separate securities, not merged
positions. VOO is benchmark/context, not required ownership or purchase permission.
These universes do not change InvestmentPolicy's current AAPL/MSFT/SPY purchase allowlist.

Quality-growth gates expose metric name/unit/basis/source/operator/threshold separately:
annual revenue growth (fraction), annual free cash flow (USD), TTM net debt/EBITDA (ratio).
Thresholds remain UNSET. MetricRule supports other company-specific metrics; it does not
require every valuation metric for every company. Duplicate latest observations or
incompatible units/bases/sources fail closed. Competitive-position and growth evidence
must be source-linked; valuation needs an available supported method/conclusion and
reviewed decision. Thesis must be active and supported. Current/proposed concentration
is checked independently; Mag7 exposure and actual holdings are explicit context.
Technology/correlation/redundancy remain unavailable without trusted reference evidence.

Long-term evaluation is monthly in the initial plan. Invalidation, weakening and sourced
deterioration in fundamentals, financial health, competition, management, catalyst or
valuation/fundamentals create EXIT_REVIEW. Price movement alone does not create a sale.

Swing entry conditions are strict inequalities: close > SMA(200), SMA(50) > SMA(200),
RSI(14) >50 and <75, and volume > prior 20 complete sessions' average. Signal-day volume
is excluded from that average. Reliable PIT histories and all warm-up windows are
required; missing volume cannot silently pass a required volume filter. Indicator
history must match the exact security. Existing TechnicalIndicatorService supplies
SMA, Wilder RSI and ATR(14); no future candles or adjustment vintages are passed.

Experimental exits: close below SMA(50), loss of trend, maximum 20 sessions/30 days,
or entry price minus 2x entry ATR. They produce review only. These values are explicit,
unapproved research defaults. A separate approval reference, risk budget and maximum
notional are required; no LLM confidence controls size. Shared FixedNotionalSizer and
independent deterministic risk still constrain any generated proposal.

## Reproduce the synthetic study

```powershell
& 'C:\Users\cesar\.codex\venvs\agentic-investing\Scripts\python.exe' -B -m experiment_lab.demo `
  --database 'C:\Users\cesar\.codex\artifacts\strategy-experiment-lab-v01\synthetic.sqlite' `
  --output docs/examples/strategy-experiment-lab-v01
```

This path contains only generated synthetic experiment data. Do not point the command
at a production/private database. No credential or network provider is used. Identical
plans retrieve the persisted completed result; they do not acquire another OOS claim.
Source changes alter the pinned code fingerprint and conflict with an existing plan ID.
Do not delete exposure records to bypass this conflict; preserve prior evidence and
review a new plan with genuinely untouched OOS dates before any new financial study.

Fixtures: 220 prior synthetic weekday sessions, followed by three six-session periods:

| Role | Start | End |
| --- | --- | --- |
| DEVELOPMENT | 2020-11-05 | 2020-11-12 |
| VALIDATION | 2020-11-13 | 2020-11-20 |
| OUT_OF_SAMPLE | 2020-11-23 | 2020-11-30 |

Dates label generated formula data, not observed historical prices. Synthetic weekdays
are not an exchange-certified holiday calendar. Fixed rise/decline/rebound segments were
defined before execution; no real bull/bear/rate-tightening/AI-market evidence is claimed.
Synthetic fundamentals and theses are prominently labeled and cannot qualify validation.
The complete exact datasets reside in ExperimentRegistry; source/version/content/lineage
pins, a relevant Python source hash and full configuration are in `plan.json`.

Twelve baseline runs = two hypotheses x three periods x two capital modes. Research
cash is USD 100,000; experimental cash is USD 160. Both retain current risk policy's
USD 160 investable sleeve. Experimental runs request fractional accounting, but policy
does not permit fractional proposals. The report makes this mismatch explicit.

All runs use next-session-close fills, 5 bps adverse slippage, 2 bps full spread,
USD 0.10 fixed commission and zero proportional commission. Human review defaults to
SKIP. Dividends/actions are absent only because the fixtures explicitly define none;
normal backtesting action-completeness and unsupported-action safeguards are unchanged.
No perfect fills, implicit approval or policy overrides are introduced.

## Preregistration and exposure protection

Trusted internal workflow:

```python
from backtesting.storage import ExperimentRegistry
from experiment_lab.storage import LabRegistry
from experiment_lab.service import StrategyExperimentLab

registry = LabRegistry(ExperimentRegistry(sqlalchemy_engine))
registry.initialize()
result = StrategyExperimentLab(registry).run(plan, datasets_by_digest)
```

`ExperimentPlan` freezes exact definitions, complete periods, planned runs, dataset pins
and validation gates. Every hypothesis/capital mode must include all three roles.
Universes, costs, policy, capital and rules cannot change between periods. Sensitivity
must match a development baseline's data/capital/costs and one predefined rule change.
Physical period datasets exclude later-period observations; earlier indicator warm-up
remains available. No current fundamentals or fabricated historical convictions are imported.

`strategy_lab_plans_v1` stores immutable plan/digest, receipts, status, final result/digest
and sanitized failure type. `strategy_lab_exposure_lock_v1` serializes reservation checks.
Existing `backtest_strategy_versions_v1` registers definitions before runs; individual
experiments retain exact configuration/dataset/result/report through ExperimentRegistry.
All initialization is additive local bootstrap, not a production migration.

RESERVED -> RUNNING -> COMPLETED or FAILED. Exposure is reserved conservatively before
evaluation; failed/crash-abandoned runs retain it. Only one caller can start a reserved
plan. Different plans cannot overlap security dates when either exposure is OOS,
regardless of dataset ID, version, lineage or strategy. Even benchmark-date overlap is
treated conservatively as exposure. The two initial hypotheses are evaluated as one
preregistered cohort, so their intentional shared holdout is disclosed up front.

No reset/relabel operation exists. This is a local audit mechanism, not proof that a
human has never seen the data or that another/deleted registry has not used it. Retain
and back up the registry. Initialization, PostgreSQL operations, authentication, restore
and production concurrency certification still require operational work.

## Sensitivity and diagnostics

Exactly three development-only swing probes, each with a separate immutable version:

- `1.0.0-sensitivity.sma`: intermediate SMA 50 -> 55.
- `1.0.0-sensitivity.rsi`: lower RSI boundary 50 -> 52.
- `1.0.0-sensitivity.atr`: ATR review multiple 2 -> 2.2.

No Cartesian combinations, repeated capital grid, return-based selection, ranking,
training or optimizer. Parameters are never changed in response to poor results.
Future intentional rule changes require a new immutable strategy version and reviewed
study design; the v0.1 initial-plan contract deliberately fixes the two baseline v1.0.0s.

Per-security diagnostics retain gate outcomes, failed/unset conditions, proposals,
rejections, risk-review coverage, entry/exit reasons, technical counts, holdings and fees.
False breakouts remain null because no approved outcome definition or sell policy exists.
High-volatility behavior retains ATR observations without inventing a regime threshold.
Sensitivity compares metric and gate-count changes without declaring a better strategy;
zero executions cannot establish return robustness or stop-exit sensitivity.

## Validation, metrics and human review

The lab runs every baseline through existing StrategyValidationReport. Aggregate
qualification uses validation/OOS evidence; development and sensitivity are reported
separately. Add mandatory replay-equality, preregistered unexposed OOS and required
risk/strategy-control gates. Human review is explicitly required even if every gate passes.
Missing mandatory controls remain UNSET / REQUIRES_REVIEW; hard failures such as synthetic
data retain FAIL / NOT_ELIGIBLE. Reproducibility compares complete deterministic results
twice, including IDs, decisions, risk outcomes, curves and metrics.

The [backtesting metric formulas](backtesting-runbook.md#metric-formulas) remain unchanged.
Added benchmark maximum drawdown = maximum of 1 - benchmark equity / running benchmark
peak on the exact same curve timestamps. Full metrics include returns/excess, drawdowns,
volatility/Sharpe/Sortino, fills/win-loss/profit factor, turnover/holding time, exposure,
utilization, largest loss/streak, risk rejection and insufficient-data counts. Undefined
values remain null; no losing experiment is dropped or rewritten.

Structured results include config/period pins, assumptions, all metrics, quality/bias,
diagnostics, USD 160 analysis, validation, sensitivity and exposure receipts. See the
[concise human review](strategy-experiment-review.md), generated
[detailed report](examples/strategy-experiment-lab-v01/human-review.md),
[plan](examples/strategy-experiment-lab-v01/plan.json) and
[results](examples/strategy-experiment-lab-v01/results.json).

The current hypotheses are NOT_ELIGIBLE. No broker submission/cancellation/modification,
production route or scheduler is enabled. Historical, OOS and synthetic sessions earn
zero credit toward at least 60 sequential non-synthetic forward-paper sessions. The clock
can begin only in a separately approved future phase; no forward paper trading is started.

The subsequent [historical review 002](historical-research-review-002.md)
qualified neither strategy: FMP historical statements returned HTTP 402,
revision provenance was unavailable, and corporate-action availability cannot
be certified. The 2026 holdout remained unexposed. Existing synthetic outputs
remain software fixtures; the 2025 Alpaca-adjusted diagnostic remains
retrospective and nonqualifying. No research threshold or v1.0.0 strategy was
retuned, and the paper clock remains zero.
