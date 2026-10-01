# SWING_TREND_MOMENTUM v1.0.0 — exploratory retrospective analysis

**Evidence class: `EXPLORATORY_RETROSPECTIVE`; strategy qualification: blocked.** The immutable v1.0.0 strategy definition and fixed research assumptions were replayed without tuning. VOO figures below are an Alpaca IEX current-vintage `adjustment=all` total-return **proxy**, not a qualified historical benchmark. The simulation uses adjusted prices as a return proxy and does not credit separate dividends. Selected-security and adjustment-vintage bias remain unresolved.

| Period / capital | Strategy return | VOO proxy | Excess | Max drawdown | Sides / round trips | Turnover | Re-entries | Average exposure |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| Development 2023–24 / $100,000 | 28.81% | 58.52% | −29.71 pp | 9.84% | 338 / 167 | 33.74× | 162 | 30.43% |
| Validation 2025 / $100,000 | 1.03% | 18.20% | −17.18 pp | 8.43% | 127 / 63 | 12.54× | 55 | 29.02% |
| Development / $160 feasibility | 82.16% | 58.52% | +23.64 pp | 31.92% | 73 / 36 | 54.36× | 32 | 47.49% |
| Validation / $160 feasibility | 18.01% | 18.20% | −0.19 pp | 25.50% | 24 / 12 | 18.31× | 9 | 44.16% |

The $160 rows are **`CAPITAL_FEASIBILITY_EXPLORATORY`**, not evidence of strategy merit: whole-share constraints concentrate exposure in low-priced names, and the simulation rejects 465 development and 230 validation orders for insufficient whole-share capital. No fractional shares are allowed. Maximum simultaneous positions were 2 and 1 respectively, versus 9 in both normalized runs. Final-cash utilization is a point-in-time value (9.35% in normalized validation, zero in $160 validation); average exposure above better describes deployment through the period. Maximum exposure was 82.85% normalized and 99.30% at $160 in validation. No policy capital cap was changed.

In normalized 2025 validation, annualized volatility was 10.57%, zero-risk-free Sharpe 0.151, and zero-target Sortino 0.205. Win rate was 41.27%; average winning round trip $721.39, average losing round trip −$476.31, and profit factor 1.064. Mean/median holding time was 11.35/12 sessions (range 1–20). The 63 exits were 31 trend failures, 23 holding-limit, and 9 ATR stops. Entry candidates used the unchanged trend, RSI, volume, and ATR conditions; all 55 observed re-entry snapshots had SMA50 above SMA200 and volume above its prior mean, with median RSI 59.43. Twenty-four re-entries occurred within five sessions, 32 within ten. Prior exits for re-entries were 27 trend failures, 22 holding-limit, and 6 ATR stops. These checks can requalify a recently exited symbol because v1.0.0 has no cooldown; no cooldown was added.

The 12.54× validation turnover includes 5.42× from re-entry buy sides (43.3% of all turnover) and 2.44× from holding-limit exit sides (19.4%). These are overlapping *behavior categories* across different trade sides and should not be summed as a causal decomposition. Modeled direct execution friction was $765.14 (0.765% of initial capital): $12.70 commissions plus approximately $752.44 from the fixed 6-bp per-side fill impact. It is an accounting estimate, not measured return lost relative to a zero-cost counterfactual. Development friction was $2,058.10. The $160 validation friction was $4.16, or 2.60% of starting cash, including $2.40 commissions. Turnover and repeated re-entry impose material cost and capital churn.

| 2025 normalized symbol | Buys / sells | Turnover | Share of turnover | Re-entries | Principal exit causes |
| --- | ---: | ---: | ---: | ---: | --- |
| PLTR | 12 / 12 | 2.40× | 19.1% | 11 | 6 trend, 5 holding |
| NVDA | 10 / 10 | 1.97× | 15.7% | 9 | 6 trend, 3 holding |
| MSFT | 8 / 8 | 1.54× | 12.3% | 7 | 6 trend |
| GOOGL | 6 / 6 | 1.23× | 9.8% | 5 | 5 holding |
| AAPL | 6 / 6 | 1.19× | 9.5% | 5 | 3 trend, 3 holding |
| META | 6 / 6 | 1.17× | 9.4% | 5 | 3 holding, 2 ATR |
| AMZN | 6 / 6 | 1.16× | 9.3% | 5 | 5 trend |
| TSLA | 6 / 5 | 1.06× | 8.4% | 5 | 2 trend, 2 ATR |
| INTC | 4 / 4 | 0.82× | 6.5% | 3 | 2 trend, 2 holding |

The $160 2025 fills were only INTC (8 sides), PLTR (12), and NVDA (4), despite technical candidates in the other symbols. This is the practical concentration problem: high-priced whole shares and a $160 sleeve make many entries impossible. The 25.50% drawdown exceeds the frozen 25% diagnostic threshold, but this sandbox does not invoke qualifying gates and cannot pass them.

Separate VOO context from the bounded raw snapshot and incomplete v0.5 ledger: 2025 raw price return **`VOO_PRICE_RETURN_EXPLORATORY` = 16.77%**; price plus nonreinvested cash distributions **`VOO_TOTAL_RETURN_ESTIMATE_EXPLORATORY` = 18.08%** (four ledger dividends, coverage/terms assumed for arithmetic). For development these are 53.99% and 57.72% (eight dividends). The proxy comparison above uses 18.20% / 58.52%, not the raw-price return. The difference between proxy and cash estimates illustrates nonidentical methodologies and incomplete qualification; none establishes an investable, historically known benchmark.

Risk Engine proposals and rejections are **not exercised** by this counterfactual simulator. It reports zero simulated policy bypasses, not a live risk-policy approval. Original corporate-action publication timestamps, complete action coverage, point-in-time adjustment vintages, selected-universe survivorship controls, and historically qualified VOO accounting remain blockers. No 2026 OOS signal, return, or benchmark was computed.

For a future human-reviewed strategy version, hypotheses to preregister before any fresh test include whether holding-limit exits cause unnecessary churn, whether immediate re-entry after trend failure or stop loss is unstable, and whether deployment and transaction costs make the strategy unattractive at $160. These are hypotheses only; no parameter, re-entry, sizing, or holding rule changed in v0.6.
