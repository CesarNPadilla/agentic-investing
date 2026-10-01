# Swing trend momentum v1.0.0 turnover diagnostic

This analyzes the already exposed normalized-capital 2025 validation ledger.
It does not rerun, retune, or change v1.0.0, and the ledger remains a
**nonqualifying retrospective counterfactual**. No 2026 holdout data was opened.

| Symbol | Entries | Exits |
| --- | ---: | ---: |
| AAPL | 6 | 6 |
| AMZN | 6 | 6 |
| GOOGL | 6 | 6 |
| INTC | 4 | 4 |
| META | 6 | 6 |
| MSFT | 8 | 8 |
| NVDA | 10 | 10 |
| PLTR | 12 | 12 |
| TSLA | 6 | 5 |

There were 64 buys, 63 sells, 63 completed round trips and one open position
at period end: 127 filled sides. Completed holding times averaged 11.35
sessions, median 12, range 1–20. Fifty-five buys were re-entries into a symbol
previously exited; the gap averaged 20.78 sessions, median 7, range 1–133.
Exit reasons: 31 trend failure, 23 holding limit, and 9 ATR stop. Maximum
simultaneous positions: nine. End-of-period cash utilization was 9.35%.

The measurable causes of 12.54x turnover are repeated re-entry across nine
symbols, trend exits, and the mandatory 20-session holding limit. The fixed
10%-of-$100,000 entry sizing makes each round trip contribute roughly 0.2x
turnover, so 63 completed round trips naturally accumulate to about 12.5x.
The 9 ATR-stop exits contribute but are not the dominant cause. The ledger
cannot establish how much signal oscillation, RSI/volume/SMA gate transitions,
or same-day sizing conflicts contributed, because rejected signals and gate
states were not retained. The trend filter accounts for 31 recorded exits,
not necessarily 31 complete oscillations. No production TradeProposal or Risk
Engine decision was made; those counts are inapplicable, not zero approvals.

At the modeled 5 bps adverse slippage plus 1 bp half spread, the 127 filled
sides imply approximately $627.04 slippage and $125.41 half-spread cost on
filled notional, plus $12.70 commissions. These are components of the modeled
fill impact, not separately observed market execution shortfall. The result
ledger does not retain exact per-session cash, rejected proposals, gate
transitions, or realized entry-to-exit P&L, so those cannot be reconstructed
without a separately preregistered diagnostic run. No rule was changed to
improve return or turnover.

The separate corrected $160 whole-share replay had 24 sides, 18.31x turnover,
25.50% drawdown and 18.01% retrospective return in validation. The tiny
capital test measures feasibility and concentrated exposure; it does not
override normalized-capital strategy assessment or authorize any order.
