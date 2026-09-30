# Backtesting & Strategy Validation Engine v0.1

Research -> Thesis -> Opportunity -> Strategy -> Backtest -> Validation -> Paper Eligibility.
Historical backtesting never authorizes live trading. This service stops before paper orders.

## Run the software demonstration

From the repository, using the documented external environment:

```powershell
& 'C:\Users\cesar\.codex\venvs\agentic-investing\Scripts\python.exe' -m backtesting.demo
```

Five explicitly synthetic sessions, one existing long-term strategy, USD 160 synthetic
experimental starting cash, USD 0.10 commission and 5 bps adverse slippage. The fixture
explicitly assumes human approval for internal simulation. These are software test
choices, not owner risk settings or investment recommendations. No optimization occurs.
Expected: COMPLETED, one internal fill, ending equity 162.8505, validation FAIL,
NOT_ELIGIBLE, zero forward-paper sessions. Performance has no investment meaning.

## Internal service

```python
from backtesting.service import BacktestingService
from backtesting.storage import ExperimentRegistry
from backtesting.models import ValidationGates

registry = ExperimentRegistry(sqlalchemy_engine)
registry.initialize()
result, report = BacktestingService(registry).run(
    config, historical_dataset, ValidationGates(), notes="Reviewed experiment purpose"
)
stored = registry.get(config.backtest_id)
```

Supply a local SQLAlchemy engine and validated records. Keep active/private databases
outside OneDrive. Bootstrap creates `backtest_experiments_v1` and
`backtest_strategy_versions_v1`; it is not a production migration. Same content is
idempotent; changed experiment IDs or strategy definitions conflict. Writes are atomic,
including version registration, with database uniqueness for concurrent duplicates.
No retry swallows persistence errors. Review scopes/authentication before exposing an API.

`BacktestConfig` v1 embeds exact StrategyVersion (ID/version/domain and all parameters)
and InvestmentPolicy (version/revision), initial capital/mode, inclusive UTC session-close
start/end dates, benchmark/basis, configured universe/scope, cadence, execution rules,
position/exposure limits, explicit development/validation/holdout periods, source metadata,
created timestamp, account scope, code identifier, annualization and risk-free assumptions.
Dates must coincide with supplied sessions; the engine never silently shortens intervals.
Null thresholds and risk-free rates are not replaced with fabricated defaults.

STRATEGY_RESEARCH allows arbitrary positive synthetic starting cash. EXPERIMENTAL limits
starting cash to USD 160. In both cases every simulated holding is explicitly attributed
to the configured strategy, and the existing USD 160 policy ceiling still constrains
acquisitions. Neither mode reads or alters actual holdings. Whole-share/buy-only policy
currently overrides the ledger's optional fractional/sell capability.

## Historical data and point-in-time enforcement

`HistoricalDataProvider.load(dataset_id, version)` returns `HistoricalDataset`. Archives
contain exact ordered exchange closes, raw OHLCV with availability timestamps,
FundamentalObservation revisions, archived ResearchObservation (assessment plus thesis),
timestamped events, CorporateAction records, adjusted SessionHistory vintages and
UniverseObservation membership records. Every archive carries ID/version/source/calendar,
reliability/sample labels and corporate-action/universe completeness attestations.

The v0.1 clock evaluates and fills at supplied session closes. Bars must be available
at that close; delayed/corrected bars fail completeness rather than being backdated.
Warm-up sessions may precede the configured interval. Holidays and early closes come
from the provider's calendar, not a Monday-Friday approximation. No provider is contacted
by the engine and no exchange-calendar certification is claimed.

`snapshot` copies only rows known at the cutoff. It checks nested evidence timestamps
against each observation's availability, including financial source/retrieval times,
thesis reviews, news and research plans. Future planned review dates are scheduling
metadata. Future revisions are excluded. Opaque reference dictionaries are rejected.
Indicators use only the latest known adjustment vintage and completed available bars;
full future history is never passed to the shared strategy or indicator service.
Provider timestamp truthfulness remains an adapter responsibility, not a proven fact.

Archived research must match the current raw mark and include a historically available
thesis with the configured account scope. Only simulated portfolio context is recomputed;
thesis, valuation, research convictions and research timestamps are never manufactured.
Missing/stale research produces explicit insufficient-data decisions. No current
fundamentals are projected backward. Event text is never executed or treated as policy.

Broad universes need historical memberships; otherwise SURVIVORSHIP_BIAS_RISK is emitted.
Configured symbols are an upper bound: memberships filter them at each cutoff. Targeted
experiments are explicitly conditional on selected securities. A provider must include
delisted securities; unsupported delisting treatment invalidates the run rather than
quietly removing their losses.

## Execution, accounting and policy

Signal at close t -> independent strategy replay and existing Risk Engine -> pending
proposal -> next supplied close t+1 -> actual cost/risk recheck -> local ledger only.
Final signals are unfilled. Decisions and fills retain proposal/opportunity IDs, strategy
version, signal/execution timestamps, reasons, checks and transaction assumptions.
Default REQUIRE_HUMAN_REVIEW handling is SKIP. Explicit ASSUME_APPROVED_FOR_SIMULATION
only admits that status; REJECT and INSUFFICIENT_DATA still cannot fill.

Buy price = raw close * (1 + (slippage_bps + spread_bps/2)/10000); sell price uses minus.
Fee = fixed commission + quantity * fill price * commission_bps/10000.
Buy limits remain binding; adverse gaps beyond a limit expire the pending proposal.
The ledger models whole/fractional long-only market accounting, but the unchanged policy
currently accepts only whole-share BUY LIMIT/DAY/CORE proposals. Existing long-term exits
remain EXIT_REVIEW; no automatic sell is invented. Swing uses the existing indicator and
strategy logic but cannot obtain forward-validation evidence from historical sessions.

Cash is gross cash with immediate **simulated** settlement, no margin/borrowing/shorting.
This is an explicitly optimistic settlement assumption, not a broker cash-account model.
Fill-time cash, exposure, symbol-value and fractional constraints apply. Costs enter
average cost; partial sells allocate basis pro rata. Closed sell fills constitute realized
trade observations, not FIFO tax lots. Dividend income is separately reported.

Splits and reverse splits multiply shares/divide per-share basis and adjust price peaks.
Split-session pending proposals are canceled rather than silently resizing instructions.
Dividends credit pre-fill holdings, preventing same-close purchases receiving prior
entitlement. v0.1 requires payment at the effective close; separate ex/pay dates need a
future receivable ledger and currently invalidate data. Unknown actions, mergers, symbol
changes and delistings also invalidate data. There is no artificial forced liquidation.

Each curve point contains cash, equity, positions, quantities, basis/average cost, market
values, unrealized/realized P&L, income, allocation, holding duration, exposure, drawdown
and benchmark equity. Trades plus archived corporate actions reconstruct the ledger.
Risk state uses the same complete PortfolioState/Transaction reconciliation contracts.

## Metric formulas

Monetary accounting uses Decimal. Ratios are fractions, drawdowns positive magnitudes.
Statistics use floating point; undefined quantities are null, not favorable substitutes.

| Metric | Formula/convention |
| --- | --- |
| Starting/ending capital | Initial cash / final cash plus marked holdings |
| Total return | Ending equity / initial capital - 1; includes fees and cash dividends |
| Annualized return | (Ending/initial)^(365.25/calendar days) - 1, only for >=365 days |
| Benchmark | Same first/last closes and sessions; frictionless buy/hold units, splits applied; price return excludes dividends, total return reinvests reliable dividends at payment close |
| Excess return | Strategy total return minus explicitly labeled benchmark return; price-return benchmark is an explicitly different basis |
| Realized/unrealized P&L | Net sell proceeds minus pro-rata acquisition basis / current value minus remaining acquisition basis |
| Trade count / wins / losses | Filled sides / positive closed sell P&L / negative closed sell P&L; open holdings do not count as wins |
| Win rate / gain / loss | Wins / closed sells; mean positive / mean negative net sell P&L |
| Profit factor | Sum positive P&L / absolute sum negative P&L; null without losses |
| Drawdown | 1 - equity / running peak (initial capital included); maximum / arithmetic mean across closes |
| Position drawdown | Largest observed per-share peak decline, adjusted for splits/cash dividends; no intraday extrema |
| Volatility | Sample standard deviation of adjacent close equity simple returns * sqrt(annual_sessions); >=2 returns |
| Downside volatility | sqrt(mean(min(return, 0)^2)) * sqrt(annual_sessions) |
| Sharpe | Mean excess session return / sample standard deviation of session returns * sqrt(annual_sessions) |
| Sortino | Mean excess session return / sqrt(mean(min(excess, 0)^2)) * sqrt(annual_sessions) |
| Risk-free conversion | (1 + configured annual risk-free rate)^(1/annual_sessions) - 1; Sharpe/Sortino null if UNSET or zero denominator |
| Turnover | Sum absolute traded notional / mean close equity (both sides count) |
| Holding period | Mean calendar days for closed sell fills; open holding ages appear separately in curve positions |
| Maximum exposure / utilization | Maximum / mean invested market value divided by equity |
| Concentration | Maximum observed symbol market value / equity |
| Largest loss / consecutive losses | Minimum negative closed P&L / longest negative closed-fill streak; breakeven breaks streak |
| Rejection / insufficient / review counts | Decision/recheck outcomes, including strategy insufficiency; multiple stages can count one proposal more than once |

## Validation and experiments

`StrategyValidationReport` retains exact strategy ID/version, backtest IDs, datasets,
periods, configurations, metrics (including benchmark/risk), quality/bias findings,
exact ValidationGates, gate outcomes and unresolved risks. Validation thresholds for
drawdown, observations, trades, turnover and acceptable quality default to UNSET.
Zero look-ahead violations and zero policy bypasses are mandatory. Synthetic evidence
always fails. At least one explicitly declared holdout is required. Remaining bias and
insufficient strategy/risk evidence require review. COMPLETED never means validation PASS.

PASS permits only ELIGIBLE_FOR_FORWARD_PAPER_VALIDATION. Nothing here authorizes orders.
All backtest/results reports record zero forward-paper sessions and a requirement for
at least 60 sequential non-synthetic forward sessions. Existing later production
qualification checks are unchanged and unsatisfied. No live eligibility status exists.

Periods must be disjoint and development precede validation/holdout. `walk_forward`
accepts explicitly supplied ordered nonoverlapping holdout folds for one frozen strategy.
Each starts fresh; curves are compared, not deceptively concatenated. No optimization,
parameter selection, training or universal-best ranking occurs. `compare` returns factual
metrics with dataset, dates and cost assumptions, so incomparable runs remain visible.

Reproducibility includes normalized input/dataset digests, immutable exact strategy and
policy, code identifier, deterministic opportunity/proposal/fill IDs, configuration time
and archived inputs. No current clock, randomness, network or broker is used by replay.
The code identifier is caller-provided and should be a reviewed revision/artifact hash.

## Limits and next work

No reliable historical data feed or historical thesis archive has been installed.
Provider provenance/calendar/adjustment attestations are not independently certified.
There is no liquidity/volume participation, intrabar stop-fill, taxes, interest, FX,
receivable/real settlement or merger/delisting recovery model. Explicitly unsupported
data fails closed. Research can evaluate larger cash balances but retains the current
USD 160 sleeve policy; unrestricted capital strategies, sells/fractions and useful swing
execution need separately reviewed simulation-policy semantics, not ad hoc bypasses.

Owner controls still needed: experimental attribution/baseline, loss ceilings, freshness,
day boundary, valuation/fit/size/concentration, strategy authorization, swing settings,
validation thresholds and optional risk-free assumptions. Database migrations, PostgreSQL
concurrency/restore and authenticated dashboard exposure remain operational work.
Recommend a provenance-validated historical provider/fixture import with real calendar,
revision-vintage and corporate-action evidence, followed by human review of policy
constraints. Do not begin paper trading or optimize strategies automatically.
