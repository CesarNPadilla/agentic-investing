# Opportunity & Strategy Engine v0.1 completion report

Implemented 2026-09-30. Production trading remains DISABLED. Stop at human risk review.

## Results

372 tests passed, 0 failed, including 61 new opportunity/strategy tests. Repository Ruff
lint passed; all 12 new/changed Python files pass formatting. Existing Starlette/httpx
deprecation warning remains. Synthetic fixtures and temporary SQLite only; no credential
files, private database, SDK logs or broker payloads were read. No order, cancellation,
modification, deployment, scheduler activation or commit was performed.

## Implementation

- Persistent InvestmentOpportunity separates thesis, valuation, catalysts, risk, fit,
  concentration, provenance and data quality. No universal stock score.
- LongTermStrategy evaluates durable 5-10+ year entries and structured exit reviews.
  SwingStrategy separately uses configurable deterministic SMA/ATR rules, stop/target,
  trend and holding-period reviews. Unset parameters block entry; no automatic sales.
- TechnicalIndicatorService provides point-in-time calendar-bound SMA, EMA, RSI, ATR,
  historical volatility, relative strength, volume averages, returns and drawdown.
- Extended data-only TradeProposal links opportunity/research/version, retains entry/exit,
  risk/rationale/evidence and concentration/capital metadata. Independent replay and existing
  deterministic risk stop at human review; confidence cannot override controls.
- Fixed-notional/ATR-bounded sizing and existing experimental accounting enforce the USD 160
  ceiling independently of portfolio value. Reservations, attribution and P/L stay explicit.
- Immutable strategy versions and atomic evaluation/audit bundles retain input snapshots,
  configuration, time, fees, experimental accounting and outcome reasons.

See [ADR-017](adr-017.md), [runbook](opportunity-strategy-runbook.md) and
[initial gap analysis](opportunity-strategy-gap-analysis.md) for decisions and field mapping.

## Files created

- strategies/__init__.py, strategies/models.py, strategies/opportunities.py
- strategies/engine.py, strategies/sizing.py, strategies/review.py
- strategies/storage.py, strategies/service.py
- technical/indicators.py
- tests/test_opportunity_strategy.py
- docs/adr-017.md, docs/opportunity-strategy-gap-analysis.md
- docs/opportunity-strategy-runbook.md, docs/opportunity-strategy-completion.md

## Files modified

- pyproject.toml: package discovery.
- risk/proposals.py: additive opportunity/version/capital/lifecycle metadata and bounded
  compatibility verification for pre-extension proposal digests.
- risk/workflow.py: opportunity evidence gate and terminal-status rejection.
- README.md, docs/architecture.md, docs/decisions.md, docs/investment-policy-v0.2.md,
  docs/roadmap.md, docs/webull-automated-trading-runbook.md, docs/codex-handoff.md:
  implemented boundary, policy notes and operating guidance.

## Remaining decisions and limitations

Unchanged owner gates: experimental baseline/attribution, daily/experimental loss limits,
risk freshness/timezone, reviewed valuation/fit/allocation/sizing, strategy authorization,
all production swing parameters and qualification evidence. Defaults were not relaxed.

No live fundamentals/news/reference/calendar adapter was added. Provider provenance and
calendars remain adapter-attested. Complete share/settlement reconciliation, ETF look-through,
point-in-time datasets, reliable fees, PostgreSQL operations and authenticated API exposure
remain pending. Percentage sizing is an interface extension, not an implemented algorithm.

Recommended next task: an offline point-in-time backtesting harness using these exact
strategy interfaces, vetted dataset/calendar vintages, next-session simulated fills, costs
and leakage tests. No broker connection or production parameter selection. This next task
has not been started; v0.1 stops for human review.
