# Initial strategy experiments: human review

**Neither strategy is eligible for forward paper validation.** These are synthetic
software checks, not investment recommendations or validated investment performance.

| Definition | Hypothesis | Rules |
| --- | --- | --- |
| LONG_TERM_QUALITY_GROWTH v1.0.0 | Durable business/fundamental quality and health can support infrequent 5–10+ year growth exposure | Monthly evaluation; separate fundamental, business, growth, thesis, valuation and portfolio gates; mandatory thresholds remain UNSET |
| SWING_TREND_MOMENTUM v1.0.0 | A simple trend/momentum framework provides a controlled research baseline | Close > SMA200; SMA50 > SMA200; 50 < RSI14 <75; volume > previous 20-session mean; ATR14/holding exit reviews |

Both definitions are BACKTEST-only and immutable. Long-term universe includes the Mag7
(GOOG and GOOGL separately), PLTR and INTC; swing excludes GOOG. VOO is the benchmark.
Experiment membership does not expand policy purchase permission or require ownership.

The study used a fixed synthetic formula with 220 warm-up weekday sessions, synthetic
fundamentals/theses and three six-session periods. No validated historical provider or
thesis archive is installed. Dates and securities were fixed before evaluation; no
real market-regime coverage or financial conclusion is claimed.

| Period | Dates | Both strategies' return | Synthetic VOO return | Strategy max drawdown | VOO max drawdown |
| --- | --- | ---: | ---: | ---: | ---: |
| Development | 2020-11-05–2020-11-12 | 0% | +2.5000% | 0% | 0% |
| Validation | 2020-11-13–2020-11-20 | 0% | -4.8594% | 0% | 4.8594% |
| Out of sample | 2020-11-23–2020-11-30 | 0% | +3.8067% | 0% | 0% |

These identical cash-only outcomes occurred in both USD 100,000 research and USD 160
experimental modes. **Zero fills are a blocked experiment, not evidence of successful
risk control or outperformance.** Annualized return, Sharpe/Sortino, win rate, average
gain/loss, profit factor and closed holding period are undefined. Volatility, turnover,
exposure and cash utilization are zero. Risk rejection count is zero because baseline
gates blocked proposals before risk submission; independent tests exercise actual risk
review/replay and prove unqualified swing proposals remain blocked.

Why entries were blocked: fundamental thresholds, valuation/fit, concentration, sizing,
strategy authorization and loss/freshness/day-boundary controls remain unapproved.
Most research-universe names are outside the unchanged purchase allowlist. Swing also
needs reviewed risk/exit controls and the existing forward-evidence gate. Diagnostics
retain every failed/unset gate and per-security outcome; none were removed after results.

Execution assumptions were next-session close, 5 bps adverse slippage, 2 bps full spread,
USD 0.10 commission and SKIP for human-review outcomes. No synthetic dividends/actions
were defined. The existing USD 160 attributed sleeve cap applies in both capital modes.
Fractional accounting was requested for USD 160 runs, but policy still forbids fractional
proposals. Synthetic AMZN/META/MSFT/TSLA prices required fractions throughout development
and OOS; META/MSFT/TSLA did throughout validation. Minimum practical size remains UNSET.
Actual simultaneous positions, transaction charges and utilization were zero.

Three fixed development-only probes changed one parameter each: SMA50->55, RSI lower
50->52, ATR multiple 2->2.2. The RSI probe changed gate counts; SMA/ATR probes did not.
All had unchanged cash-only performance. Execution/return/stop-exit fragility is therefore
**unmeasurable**, not proven robust. No probe was selected, ranked or used for tuning.

All 15 runs reproduced exactly. OOS exposure was durably reserved before evaluation
and survives failure/restart; new experiment names or dataset renames cannot reset it.
This guards the retained local registry, not research performed elsewhere. Calendar,
revision provenance, survivorship, liquidity/settlement and real historical thesis
limitations remain. Synthetic and retrospective evidence fails validation.

| Strategy | Validation | Conclusion |
| --- | --- | --- |
| LONG_TERM_QUALITY_GROWTH v1.0.0 | FAIL; mandatory controls also UNSET | NOT_ELIGIBLE |
| SWING_TREND_MOMENTUM v1.0.0 | FAIL; mandatory controls also UNSET | NOT_ELIGIBLE |

Production execution remains DISABLED. No broker orders or optimization occurred.
The required **60 sequential non-synthetic forward-paper sessions remain unsatisfied**;
historical, OOS and synthetic testing contribute zero. Human review is still required.

Next: acquire validated point-in-time market/fundamental/thesis evidence and review the
UNSET controls and simulation-policy restrictions. Do not automatically start paper trading.
Exact definitions, dataset hashes, full metrics and receipts are in the
[plan](examples/strategy-experiment-lab-v01/plan.json) and
[structured results](examples/strategy-experiment-lab-v01/results.json).
