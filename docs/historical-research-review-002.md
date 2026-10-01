# Historical research review 002, 2026-09-30

**Decision: qualification failed; no new qualifying strategy validation was
run. Both strategies remain NOT_ELIGIBLE for forward paper validation.**
The forward-paper clock is 0/60. Paper and production execution remain disabled.
The reserved 2026 OOS dataset and all OOS performance outputs stayed unexposed.

The external FMP credential loaded, but AAPL historical statement access
returned HTTP 402. Publication timestamps, amendments, and historical value
vintages therefore could not be qualified. FMP is FAIL as a qualifying
fundamental provider at present. The long-term strategy cannot be legitimately
evaluated; its missing fundamental, valuation, thesis, and portfolio-fit
dimensions remain insufficient data. No values were inferred.

A provider-neutral historical interface now separates raw prices, fundamentals,
corporate actions, and calendar closes. `HistoricalKnowledgeBoundary` classifies
each observation KNOWN, NOT_YET_KNOWN, UNCERTAIN, or UNAVAILABLE and records
non-KNOWN exclusions. It requires a proven availability instant and revision
provenance; an old fiscal period or action ex-date is insufficient. The FMP
adapter remains outside strategy logic. A new immutable Alpaca IEX raw snapshot
contains 9,823 bars for ten securities and VOO, 893 per symbol, from
2022-06-10 through 2025-12-31. It was written outside the repository at
`C:\Users\cesar\AppData\Local\AgenticInvesting\alpaca-iex-raw-2022-2025.json`.
No 2026 bar entered that snapshot. Raw prices avoid importing current adjusted
values, but corporate-action API availability is not historically certified.

The previous 2025 validation numbers remain **nonqualifying**: normalized swing
had 127 sides, +1.03% return versus VOO +18.20%, -17.18 percentage points
excess, 8.43% drawdown, and 12.54x turnover. Long-term had zero trades and
0% return versus VOO +18.20%. No new development or validation performance
numbers exist because the provider and knowledge boundary failed qualification.
Volatility, Sharpe/Sortino, win/loss, and exact risk rejection statistics were
not present in the prior counterfactual ledger and were not calculated anew.
The prior 2023–2024 development swing result was 338 sides, +28.81% versus
VOO +58.52%, 9.84% drawdown, and 33.74x turnover, also nonqualifying.

Before any future qualifying validation, the research gates are frozen in the
external immutable audit: at least 126 observations and five trade sides per
strategy, at most 25% drawdown and 3x turnover, no accepted data-quality
findings, zero look-ahead violations, zero policy bypasses, reproducible inputs,
and intact holdout. These carry forward the earlier preregistered quantitative
thresholds, with reproducibility and holdout integrity made explicit. They are
research thresholds, not Investment Policy limits. Five sides and 126 sessions
are minimal evidence floors, not proof of statistical power; 25% drawdown and
3x turnover are conservative rejection bounds rather than optimized cutoffs.
Gate status for a new qualifying run is NOT_RUN_PROVIDER_QUALIFICATION_FAILED.
The prior diagnostic's gates failed data quality/look-ahead, swing turnover,
and long-term minimum trades. No tuning followed those failures.

The audit is at
`C:\Users\cesar\AppData\Local\AgenticInvesting\historical-qualification-audit-002.json`.
It records a digest of the dev/validation-only raw snapshot, latest bar date,
frozen gate values, absence of an OOS result artifact, and disabled execution.
It does not inspect OOS prices or calculate OOS signals. Existing 2026 data
in a *prior* current-vintage adjusted export was not read in this phase and
remains disqualified as a clean holdout input.
The staged runner no longer opens OOS automatically on a validation pass;
the study method itself refuses release in this phase.

The $160 test remains separate. Whole-share affordability, one simultaneous
position in the corrected 2025 replay, 18.31x turnover, $2.40 commission,
and 25.50% drawdown show a constrained and concentrated feasibility case.
Fractional orders remain disallowed by policy; no capital rule changed.
Minimum practical notional and simultaneous signal conflicts are not established
by the saved ledger; they remain open feasibility findings.

See [FMP qualification](data-provider-qualification-fmp.md) and
[swing turnover diagnostic](swing-turnover-diagnostic-v1.md). No broker order
method or forward-paper clock was invoked.
