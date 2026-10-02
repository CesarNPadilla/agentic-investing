# H01 re-entry reset — exploratory candidate only

The preregistered `SWING_REENTRY_RESET_CANDIDATE` disarms a symbol after **every completed exit fill**. The exit session cannot arm it. A later complete post-exit session must fail the original entry predicate, and a distinct later complete session must satisfy it before the ordinary next-session counterfactual buy. There is no numerical cooldown, no change to SMA/RSI/volume/ATR/sizing, and the original 20-session holding exit remains. The [full state audit](examples/exploratory-retrospective-v08/final/h01-summary.json) and locked external result record each transition. Missing inputs cannot create a false or true event.

| Normalized $100,000 | v1.0.0 baseline | H01 candidate | Candidate minus baseline |
| --- | ---: | ---: | ---: |
| 2025 return | +1.03% | +0.45% | **−0.58 pp** |
| VOO exploratory proxy | +18.20% | +18.20% | 0 |
| Maximum drawdown | 8.43% | 7.00% | −1.43 pp |
| Trade sides / round trips | 127 / 63 | 115 / 57 | −12 / −6 |
| Turnover | 12.54× | 11.35× | −1.19× |
| Same-symbol re-entries | 55 | 49 | −6 |
| Average exit-to-re-entry lag | 20.78 sessions | 23.88 sessions | +3.10 |
| Average exposure | 29.02% | 27.61% | **−1.41 pp** |
| Maximum exposure | 82.85% | 76.45% | −6.40 pp |
| Modeled direct friction | $765.14 | $692.69 | −$72.45 |

The 2025 audit recorded 57 exit-fill disarms, 57 distinct post-exit false observations, 49 later true entry events, and **11 otherwise eligible signals suppressed while disarmed**. These 11 are *possible missed-continuation opportunities*, not 11 proven profitable trades. The lower return and exposure are adverse outcomes, so lower turnover is not grounds to accept H01. Maximum holding time stayed 20 sessions. Development also worsened in return: +18.30% candidate versus +28.81% baseline, while drawdown rose from 9.84% to 12.51%; turnover fell from 33.74× to 28.12×. The two periods do not establish robust improvement.

In 2025, candidate exit counts were 28 trend failure, 22 holding limit and 7 ATR stop; these are outcomes of changed entry timing, not changes to the exit rules. Candidate activity remained highest in NVDA (20 sides) and PLTR (20), followed by MSFT (16). Baseline PLTR had 24 sides and NVDA 20. The 2025 period informed H01's design, so this comparison is selection-biased exploratory research, not fresh validation. Current-vintage adjustments, single-venue IEX prices, incomplete corporate actions, and selected-security survivorship remain. No automatic winner is selected; H01 is not a released v1.1.0 strategy.
