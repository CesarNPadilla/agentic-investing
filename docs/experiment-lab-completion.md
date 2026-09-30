# Strategy Experiment Lab v0.1 completion

2026-09-30. Implementation and synthetic software study complete; stopped for human review.

**462 tests passed, 0 failed**, including 43 new lab cases. Repository Ruff lint passed;
all 20 changed/new Python files pass formatting. One existing Starlette/httpx warning
remains. Initial backtesting/strategy safeguard verification passed 108 focused tests.

## Definitions and implementation

Exactly two baseline hypotheses, status BACKTEST:

- **LONG_TERM_QUALITY_GROWTH v1.0.0**: monthly, 5–10+ year research horizon; separate
  fundamental quality, financial health, business quality, growth durability, valuation,
  thesis and portfolio-fit checks. Fundamental/health thresholds remain UNSET. Source,
  unit and reporting basis are mandatory; no universal score or automatic price-only sell.
- **SWING_TREND_MOMENTUM v1.0.0**: daily close > SMA200; SMA50 > SMA200; 50<RSI14<75;
  volume > prior20 average. ATR14 with 2x stop review and 20-session/30-day holding review
  are explicit experimental, unapproved parameters. Exit rules produce EXIT_REVIEW.

Shared dispatch serves current research, backtesting and independent strategy replay.
Existing TechnicalIndicatorService, FixedNotionalSizer, TradeProposal, deterministic
Risk Engine, point-in-time data and ExperimentRegistry are reused. No policy bypass,
alternative simplified backtest strategy, broker capability or API endpoint was added.

Preregistration freezes definitions, dates, universe, capital, dataset/code pins, costs,
gates and probes before evaluation. Durable exposure reservation serializes concurrent
claims and prevents overlapping OOS reuse under renamed experiments/datasets or after
failure. Development/validation/OOS period datasets are physically separated; causal
warm-up is retained. Full results replay identically and are persisted, including failures.

## Study, results and benchmark

Dataset: `LAB-SYNTHETIC-NOT-MARKET-HISTORY`, formula version 1, separately pinned
development/validation/OOS slices; synthetic research/fundamentals/theses; 220 warm-up
weekday observations. No validated historical market/thesis provider is installed.
Exact content hashes, relevant source hash and all configuration are in the
[preregistered plan](examples/strategy-experiment-lab-v01/plan.json).

| Period | Exact dates | Strategy returns, both hypotheses/modes | Synthetic VOO return | Strategy max drawdown | VOO max drawdown |
| --- | --- | ---: | ---: | ---: | ---: |
| Development | 2020-11-05–2020-11-12 | 0% | +2.5000% | 0% | 0% |
| Validation | 2020-11-13–2020-11-20 | 0% | -4.8594% | 0% | 4.8594% |
| OOS | 2020-11-23–2020-11-30 | 0% | +3.8067% | 0% | 0% |

Twelve baseline runs cover two hypotheses x three periods x research/experimental capital.
Every period has six synthetic sessions. No real bull/bear/rate-tightening/AI-market
coverage is claimed. Dates, universes and parameters were not adjusted after results.

Costs: next-session close, 5 bps adverse slippage, 2 bps full spread, USD 0.10 commission,
zero proportional fee, human-review SKIP. No dividends/actions exist in this explicitly
synthetic dataset; action-completeness safeguards remain active. Benchmark uses the exact
same dates and labeled total-return basis. Formula for its added maximum drawdown is
max(1 - benchmark equity / running benchmark peak). Other formulas remain in the
[backtesting runbook](backtesting-runbook.md#metric-formulas).

All baseline fills, turnover, strategy volatility, exposure and cash utilization are zero.
Annualized return (short periods), Sharpe/Sortino, win rate, average gain/loss, profit
factor and closed holding duration are undefined. No realized losses/streaks occurred.
Insufficient-data decisions: 10 per long-term period/mode and 54 per swing period/mode.
Risk rejection count is zero because unset entry gates prevented proposal submission;
this is not evidence of passing Risk Engine review. Tests separately exercise the real
review/replay path and confirm swing cannot fabricate forward validation.

**Cash-only curves are blocked experiments, not validated investment strategies.**
Full metrics, reasons, per-security gates, capital diagnostics, validation and receipts
are in [structured results](examples/strategy-experiment-lab-v01/results.json).

## Sensitivity and USD 160 behavior

Three predetermined development-only probes: SMA50->55 (`1.0.0-sensitivity.sma`),
RSI lower50->52 (`1.0.0-sensitivity.rsi`), ATR2->2.2 (`1.0.0-sensitivity.atr`).
Only RSI changed technical gate counts; all three left the cash-only metrics unchanged.
Return/execution/stop-exit fragility is unmeasurable while controls prevent fills.
No grid search, repeated OOS tuning, optimizer, ranking or preferred-parameter selection.

Research cash USD 100,000 remains distinct from USD 160 experimental cash, but both
retain the unchanged USD 160 investable sleeve. Fractional simulator capability is
requested in experimental runs and reported BLOCKED_BY_POLICY because policy permits
whole-share buys only. In synthetic development/OOS prices, AMZN/META/MSFT/TSLA required
fractions throughout; validation required them for META/MSFT/TSLA. Minimum practical
notional is UNSET. Actual simultaneous holdings, fees and utilization stayed zero.
No inference that larger-capital behavior transfers to USD 160 is made.

## Validation and limitations

| Hypothesis | Validation | Paper eligibility |
| --- | --- | --- |
| LONG_TERM_QUALITY_GROWTH v1.0.0 | FAIL, with mandatory controls UNSET | NOT_ELIGIBLE |
| SWING_TREND_MOMENTUM v1.0.0 | FAIL, with mandatory controls UNSET | NOT_ELIGIBLE |

All 15 runs reproduced exactly, including the three probes. Lab validation adds explicit
reproducibility, preregistered OOS and required control gates to StrategyValidationReport.
Human review always remains required. Missing mandatory controls prevent qualification;
synthetic evidence is an independent hard failure. No strategy was approved for paper.

Missing controls: fundamental/health thresholds; valuation/fit/concentration/size and
authorization; daily/experimental loss limits, freshness/day boundary; swing budgets,
policy/approval controls; validation drawdown/observation/trade/turnover/quality thresholds
and optional risk-free input. Current whole-share/buy-only policy and swing's pre-existing
forward-evidence gate constrain simulations rather than being bypassed.

Data limits: no real PIT fundamentals/theses, certified session calendar, action/revision
vintages or historical delisted universe. Fixtures are targeted and synthetic; definitions
are retrospective. No real market-regime coverage, liquidity, intrabar execution or
production settlement evidence is claimed. Technology/correlation data remain unavailable.
False-breakout classification remains UNSET. The local OOS registry cannot certify prior
human knowledge, external/deleted studies or provider truthfulness. PostgreSQL operational
validation, migrations/restore and authentication are future work.

No live trading, broker submission/cancellation/modification, production endpoint
enablement, forward-paper trading, automated optimization or deployment occurred. Existing
legacy tests separately exercise their synthetic broker fixtures; the lab has no broker
dependency and broker/network sentinels protect both new strategy implementations.

Production remains DISABLED. The **60 sequential non-synthetic forward-paper sessions
remain unsatisfied**. Historical, OOS and synthetic observations contribute zero.

Next recommended task: validated historical import with calendar/action/revision/thesis
availability provenance, followed by owner review of UNSET controls and simulation-policy
constraints. Stop for human review; do not automatically proceed to forward paper trading.

## Artifacts and files

Concise [human review](strategy-experiment-review.md), generated
[detailed review](examples/strategy-experiment-lab-v01/human-review.md), [plan](examples/strategy-experiment-lab-v01/plan.json)
and [results](examples/strategy-experiment-lab-v01/results.json). Full synthetic datasets
and experiments are stored outside OneDrive in
`C:/Users/cesar/.codex/artifacts/strategy-experiment-lab-v01/synthetic.sqlite`.

Created:

- `experiment_lab/__init__.py`, `definitions.py`, `models.py`, `storage.py`, `service.py`,
  `validation.py`, `diagnostics.py`, `fixtures.py`, `reports.py`, `demo.py`
- `strategies/experiment_models.py`, `strategies/experiments.py`, `strategies/dispatch.py`
- `tests/test_experiment_lab.py`
- `docs/adr-019.md`, `docs/experiment-lab-gap-analysis.md`, `docs/experiment-lab-runbook.md`,
  `docs/experiment-lab-completion.md`, `docs/strategy-experiment-review.md`
- `docs/examples/strategy-experiment-lab-v01/plan.json`, `results.json`, `human-review.md`

Modified:

- `strategies/models.py`: optional typed experiment parameters/diagnostics, compatible legacy serialization.
- `strategies/service.py`, `strategies/review.py`, `backtesting/engine.py`: shared dispatch and persisted gate diagnostics.
- `backtesting/analytics.py`: same-period benchmark drawdown.
- `backtesting/models.py`: explicit required human review in validation reports.
- `pyproject.toml`: package discovery for the lab.
- `README.md`, `docs/architecture.md`, `docs/decisions.md`, `docs/roadmap.md`,
  `docs/verification.md`, `docs/codex-handoff.md`.
