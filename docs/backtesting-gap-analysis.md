# Backtesting & Strategy Validation v0.1 gap analysis

Inspected the clean repository, latest handoff, policy v0.2, ADR-017, roadmap,
runbooks, strategy/proposal/review interfaces, indicators and existing simulation.

Reuse `LongTermStrategy`, `SwingStrategy`, `OpportunityEngine`,
`review_strategy_proposal`, deterministic risk, portfolio reconciliation records,
ResearchAssessment, PositionThesis and TechnicalIndicatorService. Preserve the
legacy simulator/API for compatibility; it is not qualifying evidence for this engine.

Missing: versioned reproducible experiments, cutoff-only historical snapshots,
corporate-action ledger, next-session execution with risk rechecks, reconstructable
portfolio, comprehensive analytics, explicit quality/bias findings and paper gates.

Policy constraints: whole-share BUY LIMIT/DAY/CORE proposals only; USD 160 applies
to attributed experimental inventory even in a larger synthetic research portfolio.
No sell/fractional permission is implied by simulator support. Swing's existing
forward-validation requirement remains fail-closed; historical sessions cannot
satisfy it. Unknown owner controls and validation thresholds stay UNSET.

Implement an isolated internal package with no broker/API/scheduler dependency.
Use raw execution prices and explicit actions, separately vintage adjusted indicator
history. Reject unsupported mergers, delistings and symbol changes rather than
invent proceeds. Archive historical research/theses with availability timestamps;
do not manufacture historical convictions. Default human-review handling skips fills.
Fixture demonstrations establish software behavior only, never strategy validity.
