# Historical research diagnostic 001

This is a **nonqualifying retrospective diagnostic**, not validated strategy
performance or an investment recommendation. It uses actual Alpaca IEX daily
bars for AAPL, MSFT, NVDA, AMZN, GOOGL, GOOG, META, TSLA, PLTR, INTC and VOO,
with Alpaca exchange close times and `adjustment=all`. IEX is a single-exchange
feed. The provider's adjusted history is a current-vintage download; its
historical adjustment availability is unverified. The export also lacks a
complete historical corporate-action ledger and point-in-time fundamentals.
Each retrospective cell therefore records a look-ahead finding. These results
**fail** the data-quality and zero-look-ahead validation gates.
Current-vintage adjustments can reflect corporate actions after a simulated
decision date, potentially including the reserved OOS span. No OOS strategy
returns or trades were inspected, but this data vintage cannot support a clean
holdout claim.

The frozen plan had a 2023-01-03–2024-12-31 development period (502 sessions),
2025-01-02–2025-12-31 validation (250 sessions), and reserved
2026-01-02–2026-09-29 OOS. It used $100,000 normalized research capital and a
separate $160 whole-share simulation, with VOO as benchmark. Plan digest:
`9df6e1f1180d7570dc2f7b01c02dd19ffe2ff8c579960c603aadb0dc73d197bb`.
Dataset digest:
`d1533e046a1a3f39ff064c60823a9bf90bfa64a9d18812de691095190d54087a`.

| Candidate strategy, normalized capital | Period | Trade sides | Candidate return | VOO return | Excess return | Max drawdown | Turnover |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Quality growth | Development | 0 | 0.00% | 58.52% | -58.52 pp | 0.00% | 0x |
| Swing trend momentum | Development | 338 | 28.81% | 58.52% | -29.71 pp | 9.84% | 33.74x |
| Quality growth | Validation | 0 | 0.00% | 18.20% | -18.20 pp | 0.00% | 0x |
| Swing trend momentum | Validation | 127 | 1.03% | 18.20% | -17.18 pp | 8.43% | 12.54x |

Trade count is filled **sides**, not round trips. Quality-growth remained cash
because the export supplies no publication-timestamped revenue, free-cash-flow,
debt/EBITDA, or free-cash-flow-yield observations. The swing numbers show
counterfactual signals and fills, **not Investment Policy approvals**. The
predeclared development-only probes returned +24.24% (SMA55), +30.31%
(RSI lower 52), and +30.15% (2.2× ATR), versus +28.81% baseline; all have
the same vintage limitation. No probe was selected for validation.
Across development and validation, normalized swing candidate return fell
from 28.81% to 1.03% while turnover remained above 12x; this is not evidence
of robust performance. `period-robustness-supplement.json` records the
descriptive metric shifts without opening OOS.

The $160 simulation uses whole shares and a maximum $160 deployed entry
notional. A corrective replay after a sleeve-accounting fix reports 73 swing
trade sides, +82.16% return, 31.92% maximum drawdown and 54.36x turnover in
development; validation reports 24 sides, +18.01% return, 25.50% drawdown and
18.31x turnover. These high-turnover, retrospective numbers are especially
fragile at this capital size. The original run's $160 rows are **superseded**
by `corrected-160-replay.json`; the original files were retained unchanged.
The correction did not reopen the holdout or change the research thresholds.

The frozen validation thresholds were at least 126 observations and five trade
sides per strategy, drawdown at most 25%, turnover at most 3x, no accepted
data-quality findings, zero look-ahead and zero policy bypasses. Normalized
capital passed observations and drawdown, but failed minimum trades (quality
growth), turnover (swing), data quality, and look-ahead. The $160 report also
failed drawdown in the original run; the corrected replay remains above 25%.
**Validation status: FAIL.** The OOS calculation did not run and no OOS result
file was written. Neither strategy is eligible for forward paper validation;
the 60-session clock remains at zero, and paper/production execution is disabled.

Local artifacts (outside the repository):

- `C:\Users\cesar\AppData\Local\AgenticInvesting\alpaca-iex-history-2022-2026.json`
- `C:\Users\cesar\AppData\Local\AgenticInvesting\historical-plan-001.json`
- `C:\Users\cesar\AppData\Local\AgenticInvesting\historical-results-001\`
- `C:\Users\cesar\AppData\Local\AgenticInvesting\historical-registry.sqlite`

The next admissible study needs an adapter that can attest historical
adjustment/action vintages and publication-timestamped fundamentals. It must
freeze a new plan and untouched OOS interval before examining results.
