# Backtesting & Strategy Validation Engine v0.1 completion

Date: 2026-09-30. Offline implementation ready for human review; no paper trading started.

Research -> Thesis -> Opportunity -> Strategy -> Backtest -> Validation -> Paper Eligibility.

## Verification

Full repository pytest: **419 passed, 0 failed**, including 47 new backtesting cases.
Repository Ruff lint passed; all 14 new/modified Python files pass formatting. One
existing Starlette/httpx deprecation warning remains. The external documented Python
environment, synthetic fixtures and temporary SQLite were used. No credentials,
private account records or SDK logs were read. No dependency changes were required.

The [deterministic demo](examples/backtesting-demo-result.json) contains five synthetic
sessions and one internal fill. Initial cash 160; final equity 162.8505; validation FAIL,
NOT_ELIGIBLE; zero forward-paper sessions. No investment conclusions are possible.
Parameters were not optimized or selected for attractive returns.

## Architecture and contracts

- Provider-neutral HistoricalDataset archives -> materialized cutoff-only views -> existing
  OpportunityEngine / LongTermStrategy / SwingStrategy -> TradeProposal -> independent
  strategy replay and deterministic Risk Engine -> next-session simulation -> portfolio
  history/analytics -> separate StrategyValidationReport. See [ADR-018](adr-018.md).
- BacktestConfig v1 embeds exact strategy/version/domain/parameters, risk policy/version,
  capital mode, dates, benchmark/basis, universe, cadence, commissions/slippage/spread,
  fractional flag, cash/session rules, position/exposure ceilings, periods, source metadata,
  creation time, code identifier and optional statistical assumptions. JSON roundtrips.
- Historical interfaces cover raw OHLCV, exact sessions, available-at fundamentals,
  archived research/theses, events, corporate actions, historical universe membership
  and adjusted indicator vintages. Nested timestamps are checked; future rows are never
  passed to strategy evaluation. No historical theses or current-as-historical financials
  are fabricated. The strategy's original creation timestamp is preserved on replay.
- Signal review and actual-fill risk checks both use existing deterministic policy.
  Default human-review handling skips fills. Explicit assumed approval admits only
  REQUIRE_HUMAN_REVIEW in internal simulation, never REJECT/INSUFFICIENT_DATA. Costs,
  limits, cash and exposure are checked at the next supplied session close.
- Portfolio accounting tracks gross cash, holdings, basis, realized/unrealized P&L,
  dividend income, equity, allocations, exposures, drawdowns, holding ages and trades.
  Existing PortfolioState/Transaction records reconcile fills and corporate actions.
- Performance/risk formulas, benchmark bases and undefined-value conventions are fully
  documented in the [runbook metric table](backtesting-runbook.md#metric-formulas).
  Outputs include equity/benchmark/drawdown/allocation histories and full fill attribution.
- StrategyValidationReport retains experiments/datasets/periods/assumptions, performance,
  risk/benchmark metrics, quality, bias warnings, exact gates/results, unresolved risks and
  paper eligibility. Completion is independent of validation. Missing mandatory gates
  remain UNSET, synthetic evidence fails, and historical sessions never count as forward.
- ExperimentRegistry atomically stores full inputs/results/reports and immutable strategy
  definitions. Same inputs reproduce complete results, including IDs/digests. Code revision
  is explicit caller metadata. BacktestingService exposes internal run and explicit frozen
  holdout-fold comparison; no optimizer, scheduler, dashboard or broker is introduced.

## Deliberately enforced limitations

The current policy allows whole-share buy proposals only, with a USD 160 attributed
experimental ceiling. Synthetic research starting capital is independently configurable,
but does not relax that ceiling. Internal sell/fraction accounting is tested; existing
policy does not authorize those proposals. Long-term exits remain review-only. Swing
backtests can evaluate shared rules/indicators, but fills remain blocked by its existing
60-session forward-evidence requirement. These restrictions require a separate reviewed
simulation-policy design; this implementation does not bypass them to manufacture trades.

Splits/reverse splits and same-close cash dividends are supported. Separate ex/pay-date
dividends, mergers, symbol changes and delistings explicitly invalidate data. Raw prices
must be accompanied by a complete corporate-action attestation; adjusted histories are
used separately for indicators. Immediate simulated settlement, no liquidity/participation,
no intrabar fills/taxes/FX, and adapter-attested calendars remain model limitations.

Reliable historical fundamentals, historical theses, provider/calendar vintages and
historical universes have not been installed. Broad runs without point-in-time membership
flag SURVIVORSHIP_BIAS_RISK; targeted runs are conditional on selected symbols. Timestamp
truthfulness and undeclared provider revisions cannot be independently proven by a schema.
Nested future-known evidence fails with LOOKAHEAD_VIOLATION. Unknown/unsupported data
cannot silently produce a passing validation report. PostgreSQL operational validation
and future API scope authorization remain outstanding.

## Safety and remaining policy decisions

Risk Engine reuse is verified at signal and fill stages. The Backtesting Engine never
invoked submit_order, submit_limit_order, place_order or equivalent broker execution.
Static boundary tests and runtime broker/network sentinels guard this. The full legacy
suite separately tests its existing synthetic broker; no actual broker orders occurred.
Production trading remains disabled. No live eligibility status, credentials, paper order,
production order, automated optimization, deployment or commit was introduced.

The requirement for **at least 60 sequential non-synthetic forward-paper sessions remains
unsatisfied**. Every backtest/report records zero credit toward it. No strategy is approved
for production and the synthetic demonstration is not eligible for forward paper validation.

Unresolved owner controls: real experimental attribution/baseline; daily and experimental
loss limits; freshness and timezone; reviewed valuation/fit/sizing/concentration and
strategy authorization; swing controls; validation drawdown, minimum observations/trades,
turnover and acceptable-quality thresholds; optional risk-free assumptions. Fixture choices
do not set owner policy. Older independent production qualification thresholds are unchanged.

Recommended next task: a provenance-validated historical provider/import with corporate
action, exchange-calendar and revision-vintage tests, followed by human policy review of
the documented simulation constraints. Do not automatically proceed to paper trading.

## Files created

- `backtesting/__init__.py`
- `backtesting/models.py`
- `backtesting/data.py`
- `backtesting/engine.py`
- `backtesting/portfolio.py`
- `backtesting/analytics.py`
- `backtesting/validation.py`
- `backtesting/storage.py`
- `backtesting/service.py`
- `backtesting/demo.py`
- `tests/test_backtesting.py`
- `docs/adr-018.md`
- `docs/backtesting-gap-analysis.md`
- `docs/backtesting-runbook.md`
- `docs/backtesting-completion.md`
- `docs/examples/backtesting-demo-result.json`

## Files modified

- `risk/evaluator.py`: additive date serialization in the shared digest; datetime encoding preserved.
- `strategies/engine.py`, `strategies/review.py`: explicit historical replay option; default current behavior preserved.
- `pyproject.toml`: package discovery includes backtesting.
- `README.md`
- `docs/architecture.md`
- `docs/decisions.md`
- `docs/roadmap.md`
- `docs/backtesting-paper-trading.md`: labels the separate legacy workflow.
- `docs/verification.md`
- `docs/codex-handoff.md`: latest implementation, verification, limitations and next task.
