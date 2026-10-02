# Proposed $1,000 whole-share feasibility — simulation only

The unchanged swing v1.0.0 was replayed using **$1,000 simulated capital** under the existing [preregistered plan](examples/exploratory-retrospective-v07/capital-feasibility-plan.json). This is `CAPITAL_FEASIBILITY_EXPLORATORY`, not strategy merit or an approved policy limit. The current Investment Policy still caps attributed experimental capital at $160; no deposit is assumed, no fractional shares are enabled, and the real portfolio is separate. Normalized $100,000 research and locked $160 results remain untouched.

| 2025 feasibility | Preserved $160 | New simulated $1,000 |
| --- | ---: | ---: |
| Unaffordable whole-share orders | 230 | **142** |
| Symbols with fills | INTC, NVDA, PLTR | AAPL, AMZN, GOOGL, INTC, META, NVDA, PLTR, TSLA |
| Trade sides / round trips | 24 / 12 | 54 / 27 |
| Maximum simultaneous positions | 1 | 3 |
| Average exposure | 44.16% | 59.87% |
| Maximum exposure | 99.30% | 98.83% |
| Maximum single-name concentration | 99.30% | 98.83% |
| Turnover | 18.31× | 31.56× |
| Modeled direct friction | $4.16 | $24.34 |
| Maximum drawdown | 25.50% | 10.99% |
| Simulated return | +18.01% | +17.09% |

The $1,000 replay filled eight symbols instead of three, but **MSFT still received no fill** and 142 entries were unaffordable or blocked by available simulated cash. More capital improved whole-share reach and average exposure but did not remove near-total single-name concentration at some points. The larger absolute friction was 2.43% of starting capital (versus 2.60% at $160). Turnover increased, while return was lower than the $160 path; these paths have different feasible holdings and cannot establish a strategy-quality improvement. Development $1,000 had 316 skips, 151 sides, 5 maximum positions, 26.12% drawdown, and 33.71% return; this is not a claim of robustness.

The [capital summary](examples/exploratory-retrospective-v08/final/capital_feasibility-summary.json) records whole-share skips by symbol and the locked result digest. There were no real orders, no Risk Engine approvals/rejections, and no Investment Policy change. Both paper and production execution remain disabled; forward paper is 0/60; 2026 OOS is sealed.
