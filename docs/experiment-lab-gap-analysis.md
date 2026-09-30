# Strategy Experiment Lab v0.1: pre-implementation gap analysis

2026-09-30. Inspected the clean repository, latest handoff, ADR-018, policy v0.2,
roadmap/runbooks, strategy/proposal/risk interfaces, point-in-time data, registry,
validation and tests. Baseline: 108 focused strategy/backtesting tests passed.

Reuse BacktestEngine, cutoff-only views, TechnicalIndicatorService, shared strategy
proposal/sizing, independent Risk Engine replay, immutable ExperimentRegistry and
StrategyValidationReport. Do not introduce broker connectivity or another simulator.

Gaps: no named quality-growth or trend-momentum hypotheses; generic SMA swing rules
do not implement 50/200, RSI or volume conditions. Missing visible dimension gates,
preregistered multi-period plans, out-of-sample exposure receipts, bounded sensitivity
plans, structured diagnostics and human review artifacts. Existing validation also
needs explicit reproducibility and required-risk-configuration evidence for lab use.

Historical provider limitations remain: no verified historical fundamentals/theses,
calendar/action vintages or complete delisted universe. Demonstrations must be labeled
synthetic; no real bull/bear/rate/AI-regime coverage can be claimed. Missing owner
thresholds stay UNSET. Research universes do not grant purchase authorization.

Policy constraints remain whole-share buys, USD 160 attributed capital and swing's
forward-evidence gate. Simulator fractional support does not override policy. Larger
synthetic research cash will be reported separately without silently expanding the
agent sleeve. If these restrictions block hypotheses, preserve that negative outcome.

Implement exactly two baseline definitions (1.0.0), extend shared strategy dispatch,
freeze plans before evaluation, reserve all selected data exposure before reading
results, and permit only a small declared development-only sensitivity neighborhood.
No tuning, automatic ranking, production eligibility or forward-paper session credit.
