# H04 fixed transaction-cost sensitivity — unchanged v1.0.0

Exactly the three v0.7 preregistered scenarios were run on the unchanged swing v1.0.0. The simulator applies slippage plus **half of the full spread per side** to next-session-close fills. The same dataset, universe, periods, $100,000 capital, signals, and VOO current-vintage adjusted-all exploratory proxy were used. The cost scenarios were not selected or adjusted after observing returns.

| 2025 scenario | Commission / full spread / slippage | Return | Sides / round trips | Turnover | Max drawdown | Average exposure | Direct modeled friction |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Matched no-cost | $0 / 0 / 0 bps | +1.7877% | 127 / 63 | 12.5419× | 8.23% | 28.91% | $0 |
| Baseline | $0.10 / 2 / 5 bps | +1.0262% | 127 / 63 | 12.5407× | 8.43% | 29.02% | $765.14 |
| Stressed | $0.25 / 4 / 10 bps | +0.2712% | 127 / 63 | 12.5379× | 8.63% | 29.12% | $1,536.29 |

The matched **no-cost minus baseline simulated return difference is +0.7615 percentage points** in 2025. It is a genuine matched counterfactual result within this deterministic model, distinct from the baseline's $765.14 sum of direct fill impact and commissions. Trades had the same symbol/side sequence and count, but fill prices, quantities/notional, turnover and exposure differed; therefore the difference need not equal direct friction divided by starting cash exactly. Baseline commissions were $12.70 and modeled fill impact approximately $752.44. Development returns were +30.84%, +28.81%, and +26.73% for no-cost, baseline and stressed respectively; all had 338 sides. Higher costs worsened both periods' modeled return. No cost scenario was chosen to favor H01; H01 used baseline costs.

The [H04 summary](examples/exploratory-retrospective-v08/final/h04-summary.json) preserves all six scenario-period cells. VOO is an `EXPLORATORY_NONQUALIFYING_BENCHMARK`; the result is not a historical estimate of actual achievable execution costs. Current-vintage prices, IEX venue coverage, corporate-action gaps, and research-informed 2025 limit inference. No automatic scenario or strategy winner is selected.
