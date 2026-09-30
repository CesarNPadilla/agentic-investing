# Strategy Experiment Lab v0.1 — human review

**SYNTHETIC SOFTWARE EXPERIMENTS — NOT INVESTMENT RECOMMENDATIONS.**

The dates below label generated fixtures, not observed market performance.
No optimization, winner selection, broker orders or forward-paper trading occurred.

Plan: `strategy-experiment-lab-v1-synthetic`; immutable fingerprint: `564bfea6e20a3bb7ad842ec3b36d7299baca1b80aa8e5797cd68425e7b324fe6`.

Research → Thesis → Opportunity → Strategy → Backtest → Validation → Human Review → Future Paper Eligibility.

## Data and assumptions

Period datasets are physically separated; only earlier indicator warm-up is retained. Synthetic calendars are not exchange-certified.

| Role | Start | End |
| --- | --- | --- |
| development | 2020-11-05 | 2020-11-12 |
| validation | 2020-11-13 | 2020-11-20 |
| out_of_sample | 2020-11-23 | 2020-11-30 |

Execution assumptions: [&quot;{&#x27;timing&#x27;: &#x27;next_session_close&#x27;, &#x27;commission_fixed&#x27;: &#x27;0.10&#x27;, &#x27;commission_bps&#x27;: &#x27;0&#x27;, &#x27;slippage_bps&#x27;: &#x27;5&#x27;, &#x27;spread_bps&#x27;: &#x27;2&#x27;, &#x27;fractional_shares&#x27;: False, &#x27;cash_rule&#x27;: &#x27;no_borrowing_instant_simulated_settlement&#x27;, &#x27;session_rule&#x27;: &#x27;supplied_exchange_closes&#x27;, &#x27;human_review&#x27;: &#x27;SKIP&#x27;, &#x27;max_exposure&#x27;: &#x27;1&#x27;, &#x27;max_position_value&#x27;: None}&quot;, &quot;{&#x27;timing&#x27;: &#x27;next_session_close&#x27;, &#x27;commission_fixed&#x27;: &#x27;0.10&#x27;, &#x27;commission_bps&#x27;: &#x27;0&#x27;, &#x27;slippage_bps&#x27;: &#x27;5&#x27;, &#x27;spread_bps&#x27;: &#x27;2&#x27;, &#x27;fractional_shares&#x27;: True, &#x27;cash_rule&#x27;: &#x27;no_borrowing_instant_simulated_settlement&#x27;, &#x27;session_rule&#x27;: &#x27;supplied_exchange_closes&#x27;, &#x27;human_review&#x27;: &#x27;SKIP&#x27;, &#x27;max_exposure&#x27;: &#x27;1&#x27;, &#x27;max_position_value&#x27;: None}&quot;].
Capital modes/cash: [(&#x27;EXPERIMENTAL&#x27;, &#x27;160&#x27;), (&#x27;STRATEGY_RESEARCH&#x27;, &#x27;100000&#x27;)]. Current policy permits only whole-share buys and USD 160 attributed acquisitions; larger synthetic research cash does not expand that sleeve.

All dataset pins, exact definitions, assumptions, metrics, diagnostics and exposure receipts are in the JSON artifact and local registry.

## LONG_TERM_QUALITY_GROWTH v1.0.0

Domain: LONG_TERM; status: BACKTEST.

Hypothesis: durable growth, business/fundamental quality and financial health can support infrequent 5–10+ year allocations with reviewed valuation and portfolio fit.
Rules: separately sourced fundamental, financial-health and growth gates; business/growth evidence; supported active thesis; valuation and concentration review. Exact thresholds: [(&#x27;revenue_growth&#x27;, &#x27;ge&#x27;, &#x27;UNSET&#x27;), (&#x27;free_cash_flow&#x27;, &#x27;ge&#x27;, &#x27;UNSET&#x27;), (&#x27;net_debt_to_ebitda&#x27;, &#x27;le&#x27;, &#x27;UNSET&#x27;)].
Thesis/fundamental/health/catalyst deterioration creates EXIT_REVIEW, never a price-only automatic sell.

Universe: AAPL, MSFT, NVDA, AMZN, GOOGL, GOOG, META, TSLA, PLTR, INTC. Research membership grants no purchase permission. VOO is the benchmark, not a required holding.

| Period | Capital mode | Return | VOO return | Max drawdown | VOO drawdown | Fills | Utilization |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |
| development | STRATEGY_RESEARCH | 0 | 0.0250000000000000000000 | 0 | 0 | 0 | 0 |
| validation | STRATEGY_RESEARCH | 0 | -0.0485944976076555023923444976 | 0 | 0.0485944976076555023923444976 | 0 | 0 |
| out_of_sample | STRATEGY_RESEARCH | 0 | 0.038067122436295835922933499 | 0 | 0 | 0 | 0 |
| development | EXPERIMENTAL | 0 | 0.0250000000000000000000000 | 0 | 0 | 0 | 0 |
| validation | EXPERIMENTAL | 0 | -0.0485944976076555023923444975 | 0 | 0.0485944976076555023923444975 | 0 | 0 |
| out_of_sample | EXPERIMENTAL | 0 | 0.038067122436295835922933499 | 0 | 0 | 0 | 0 |

Diagnostics: concentration:UNSET, free_cash_flow:UNSET, net_debt_to_ebitda:UNSET, portfolio_fit:UNSET, purchase_permission:FAIL, revenue_growth:UNSET, valuation:UNSET.

What happened: 0 filled sides across independent baseline runs. Risk review exercised=False. Zero fills/cash-only curves do not demonstrate strategy success. Gate failures above explain blocked entries; unit tests separately exercise risk submission paths.
Largest weaknesses: unresolved controls listed below, policy/universe restrictions and no production-grade liquidity/settlement model. No closed trades means undefined win rate/profit factor/holding period; an UNSET risk-free rate or zero variance prevents meaningful Sharpe/Sortino values.
Bias review: [&#x27;CONDITIONAL_ON_SELECTED_SECURITIES&#x27;, &#x27;HISTORICAL_SESSIONS_DO_NOT_COUNT_TOWARD_60_FORWARD_SESSIONS&#x27;, &#x27;IN_SAMPLE_EVALUATION&#x27;, &#x27;RETROSPECTIVE_STRATEGY_DEFINITION&#x27;, &#x27;SYNTHETIC_CAPITAL_SEPARATE_FROM_REAL_PORTFOLIO_POLICY_CAP_STILL_APPLIES&#x27;]. Synthetic results provide no real bull/bear/rate-tightening/AI-expansion coverage. OOS exposure was reserved before evaluation and cannot be relabeled unseen.
Data quality: [&#x27;SYNTHETIC_TEST_DATA&#x27;].
USD 160 behavior: fractional requirements and whole-share prices are listed per period in JSON. Fractional orders remain blocked by policy; minimum practical size is UNSET. No claim that USD 100,000 behavior translates to USD 160.

Validation: **FAIL**. Conclusion: **NOT_ELIGIBLE**. Human review remains required.
Unresolved controls: INSUFFICIENT_STRATEGY_OR_RISK_EVIDENCE, RETROSPECTIVE_STRATEGY_DEFINITION, UNSET:entry.concentration_ceiling, UNSET:entry.fixed_notional, UNSET:entry.portfolio_fit_decision, UNSET:entry.valuation_decision, UNSET:fundamental.free_cash_flow, UNSET:fundamental.net_debt_to_ebitda, UNSET:fundamental.revenue_growth, UNSET:risk_policy.daily_loss_timezone, UNSET:risk_policy.max_daily_loss, UNSET:risk_policy.max_experimental_loss, UNSET:risk_policy.max_state_age_seconds, UNSET:strategy.authorization_reference.

## SWING_TREND_MOMENTUM v1.0.0

Domain: SWING; status: BACKTEST.

Hypothesis: a simple, unoptimized trend/momentum framework is a useful controlled research baseline.
Rules: close > SMA(200), SMA(50) > SMA(200), 50 < RSI(14) < 75; volume filter=True, prior 20 sessions. ATR(14), 2× entry-ATR stop, 20 sessions/30 days are explicit experimental review parameters.
Review exits on close below intermediate SMA, trend failure, holding limit or ATR stop. Existing swing forward-evidence gate remains enforced.

Universe: AAPL, MSFT, NVDA, AMZN, GOOGL, META, TSLA, PLTR, INTC. Research membership grants no purchase permission. VOO is the benchmark, not a required holding.

| Period | Capital mode | Return | VOO return | Max drawdown | VOO drawdown | Fills | Utilization |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |
| development | STRATEGY_RESEARCH | 0 | 0.0250000000000000000000 | 0 | 0 | 0 | 0 |
| validation | STRATEGY_RESEARCH | 0 | -0.0485944976076555023923444976 | 0 | 0.0485944976076555023923444976 | 0 | 0 |
| out_of_sample | STRATEGY_RESEARCH | 0 | 0.038067122436295835922933499 | 0 | 0 | 0 | 0 |
| development | EXPERIMENTAL | 0 | 0.0250000000000000000000000 | 0 | 0 | 0 | 0 |
| validation | EXPERIMENTAL | 0 | -0.0485944976076555023923444975 | 0 | 0.0485944976076555023923444975 | 0 | 0 |
| out_of_sample | EXPERIMENTAL | 0 | 0.038067122436295835922933499 | 0 | 0 | 0 | 0 |

Diagnostics: concentration:UNSET, exit_parameters:UNSET, price_above_trend:FAIL, purchase_permission:FAIL, rsi_lower:FAIL, volume_confirmation:FAIL.

What happened: 0 filled sides across independent baseline runs. Risk review exercised=False. Zero fills/cash-only curves do not demonstrate strategy success. Gate failures above explain blocked entries; unit tests separately exercise risk submission paths.
Largest weaknesses: unresolved controls listed below, policy/universe restrictions and no production-grade liquidity/settlement model. No closed trades means undefined win rate/profit factor/holding period; an UNSET risk-free rate or zero variance prevents meaningful Sharpe/Sortino values.
Bias review: [&#x27;CONDITIONAL_ON_SELECTED_SECURITIES&#x27;, &#x27;HISTORICAL_SESSIONS_DO_NOT_COUNT_TOWARD_60_FORWARD_SESSIONS&#x27;, &#x27;IN_SAMPLE_EVALUATION&#x27;, &#x27;RETROSPECTIVE_STRATEGY_DEFINITION&#x27;, &#x27;SYNTHETIC_CAPITAL_SEPARATE_FROM_REAL_PORTFOLIO_POLICY_CAP_STILL_APPLIES&#x27;]. Synthetic results provide no real bull/bear/rate-tightening/AI-expansion coverage. OOS exposure was reserved before evaluation and cannot be relabeled unseen.
Data quality: [&#x27;SYNTHETIC_TEST_DATA&#x27;].
USD 160 behavior: fractional requirements and whole-share prices are listed per period in JSON. Fractional orders remain blocked by policy; minimum practical size is UNSET. No claim that USD 100,000 behavior translates to USD 160.

Validation: **FAIL**. Conclusion: **NOT_ELIGIBLE**. Human review remains required.
Unresolved controls: INSUFFICIENT_STRATEGY_OR_RISK_EVIDENCE, RETROSPECTIVE_STRATEGY_DEFINITION, UNSET:entry.concentration_ceiling, UNSET:entry.portfolio_fit_decision, UNSET:entry.valuation_decision, UNSET:risk_policy.daily_loss_timezone, UNSET:risk_policy.max_daily_loss, UNSET:risk_policy.max_experimental_loss, UNSET:risk_policy.max_state_age_seconds, UNSET:sizing.max_notional, UNSET:sizing.risk_budget, UNSET:strategy.authorization_reference, UNSET:swing.parameters_approved_reference, UNSET:swing_policy.max_holding_days, UNSET:swing_policy.max_loss, UNSET:swing_policy.max_position_capital, UNSET:swing_policy.stop_rule.

## Limited sensitivity

Preregistered development-only, one-factor probes: SMA(50)→55; RSI lower bound 50→52; ATR multiple 2→2.2. No Cartesian combinations, ranking, tuning or automatic selection.

- 1.0.0-sensitivity.sma: technical gate counts changed=False; metric differences={}. Behavioral probe only; execution fragility is unmeasurable while mandatory controls block fills.
- 1.0.0-sensitivity.rsi: technical gate counts changed=True; metric differences={}. Behavioral probe only; execution fragility is unmeasurable while mandatory controls block fills.
- 1.0.0-sensitivity.atr: technical gate counts changed=False; metric differences={}. Behavioral probe only; execution fragility is unmeasurable while mandatory controls block fills.

## Human review boundary

Conclusions: {&#x27;LONG_TERM_QUALITY_GROWTH&#x27;: &#x27;NOT_ELIGIBLE&#x27;, &#x27;SWING_TREND_MOMENTUM&#x27;: &#x27;NOT_ELIGIBLE&#x27;}. Zero historical/OOS/synthetic sessions count toward the required **60 sequential non-synthetic forward-paper market sessions**. Production execution remains DISABLED.
Next: acquire provenance-validated historical market/fundamental/thesis evidence and review the UNSET controls and simulation-policy constraints. Do not begin forward paper trading automatically.
