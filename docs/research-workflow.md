# Technical, portfolio, risk, and research-report workflow

Long-Term Research Agent v0.1 is an additional internal service with persistent assessments,
thesis history and targeted daily/quarterly cycles. See its [runbook](long-term-research-runbook.md).
The HTTP report workflow below is retained unchanged; it does not automatically invoke the
new agent or expose private assessments.

For strategy evaluation after research, see [Phase 3 backtesting and paper trading](backtesting-paper-trading.md).

The existing `POST /research/{symbol}` now accepts four optional evidence sections:
`fundamentals`, `news`, `price_history`, and `portfolio`. Each section can be submitted
independently. Quotes still come from the configured market provider. Supplied history
takes priority over provider history. No broker credentials or LLM are involved.

## End-to-end example

With the local API running, from the project root in PowerShell:

```powershell
$researchPython = 'C:\Users\cesar\.codex\venvs\agentic-investing\Scripts\python.exe'
$body = (& $researchPython docs/examples/build_full_evidence.py) -join "`n"
$report = Invoke-RestMethod -Method Post 'http://127.0.0.1:8000/research/AAPL' `
    -ContentType 'application/json' -Body $body
$report.technicals
$report.portfolio
$report.risk_findings
$report.assessment
Invoke-WebRequest "http://127.0.0.1:8000/reports/$($report.id)?format=markdown" `
    -OutFile research-report.md
```

The generator prints entirely synthetic evidence with fixed September 2026 dates;
freshness warnings change with the report date. It includes 60 weekday closes (not
an exchange-calendar-verified series) and a USD 5,000 portfolio: USD 1,590 AAPL,
USD 500 MSFT, and USD 2,910 cash. AAPL exposure is 31.8%, total gross exposure 41.8%,
and cash weight 58.2%. The existing quote fixture is independent of these illustrative
position prices; exposure always uses snapshot prices. The Markdown download uses
the persisted report and never refreshes prices or recomputes old findings.

See [the fundamentals/news contract](research-evidence.md) for those sections.

## Technical indicators

Imported `price_history` requires `symbol`, `source`, `adjustment` (`split`, `all`,
or `raw`), `is_sample`, and `bars`. Each bar has a timezone-aware `timestamp` and a
positive finite Decimal `close`. Maximum: 5,000 bars. Bars must be chronological,
unique, and limited to one observation per New York calendar day. This workflow
targets US equity daily observations; UTC-midnight date labels should be converted
to the intended New York session timestamps before import.

Current New York calendar-day and future bars are excluded from calculations,
even after market close. Original submitted bars remain stored in `price_history`;
`technicals.bars_used` and `as_of` describe the actual calculation subset. Raw history
raises a corporate-action warning; split-only history excludes dividends. Calendar
gaps are not filled, and no exchange-session completeness claim is made.

| Output | Convention | Minimum closes |
| --- | --- | --- |
| `sma20`, `sma50` | Arithmetic mean of final 20/50 closes | 20/50 |
| `rsi14` | Wilder smoothing; first 14 gains/losses averaged, then 1/14 smoothing | 15 |
| `macd` | EMA12 - EMA26, each seeded with its initial period SMA | 26 |
| `macd_signal` | EMA9 of valid MACD values, seeded with their SMA | 34 |
| `macd_histogram` | MACD - signal | 34 |
| `bollinger_upper`, `bollinger_lower` | SMA20 +/- 2 population standard deviations | 20 |
| `return_20` | Latest close / close 20 observations earlier - 1 | 21 |
| `volatility_20_annualized` | Sample standard deviation of 20 simple returns x sqrt(252) | 21 |
| `max_drawdown` | Most negative close/running peak - 1 over supplied eligible history | 2 |
| `drawdown_from_peak` | Last close / highest eligible close - 1 | 2 |

All calculations use Decimal arithmetic. RSI is 50 for flat history, 100 when gains
exist without losses, and 0 when only losses exist. Missing warm-up data produces
null outputs and named `missing_indicators`. SMA comparison describes the final
levels; it does not claim a crossover occurred. Drawdowns are negative fractions.
The annualization factor assumes 252 sessions; gaps can distort this descriptive
estimate. The history window and EMA seed can produce differences from chart vendors.
ATR, VWAP, and volume indicators are not computed from close-only inputs.

Formula references: [Fidelity RSI](https://www.fidelity.com/learning-center/trading-investing/technical-analysis/technical-indicator-guide/RSI),
[Fidelity MACD](https://www.fidelity.com/learning-center/trading-investing/technical-analysis/technical-indicator-guide/macd),
and [Fidelity Bollinger Bands](https://www.fidelity.com/learning-center/trading-investing/technical-analysis/technical-indicator-guide/bollinger-bands).
The seed, flat-series, missing-history, and variance conventions above are explicit
project implementation choices.

## Portfolio exposure

`portfolio` is a read-only snapshot requiring `source`, timezone-aware `as_of`,
three-letter `currency`, `holdings`, and `cash`. Set `is_sample` for synthetic data.
Empty holdings/cash arrays represent an explicitly supplied empty balance; absence
of the entire section means exposure is unavailable.

Each holding has `account_id`, `symbol`, signed share `quantity`, positive `price`,
`price_as_of`, `price_source`, `currency`, and optional `sector`. `asset_type` is
`equity`; derivatives are rejected. Negative quantities represent short positions.
Each cash row has `account_id`, `currency`, and signed `amount`; negative cash can
represent borrowing. Maximum: 1,000 holdings and 1,000 cash rows.

All values must already be in the snapshot currency. Mixed currencies are rejected;
there is no automatic FX conversion. Consolidate lots into one row per account/symbol
and cash into one row per account. Repeated symbols across accounts are supported.
Sector labels must agree for a symbol across accounts; use a consistent taxonomy
and spelling. Unknown sectors are preserved as `Unknown`, not silently dropped.
Position prices must not postdate the snapshot. Snapshot and price ages over 24 hours
generate warnings, including weekends; this is an explicit freshness heuristic.

| Output | Calculation |
| --- | --- |
| Position market value | Signed quantity x supplied price |
| `long_value` | Sum of positive position values |
| `short_value` | Magnitude of negative position values |
| `gross_exposure` | Long value + short value |
| `net_exposure` | Long value - short value |
| `equity` | Net exposure + signed cash |
| Gross/net leverage | Gross/net exposure / positive equity |
| `cash_weight` | Signed cash / positive equity |
| Group net/gross weights | Group net/gross invested value / positive equity |

`by_symbol`, `by_sector`, and `by_account` aggregate **position exposure**; account
groups exclude cash. Opposite positions across accounts offset in net value but
remain in gross value. All weights use total portfolio equity, including cash, as
the denominator. Gross weights can exceed 100%. Cash-only snapshots are supported.
Nonpositive equity leaves weights/leverage null while retaining signed values.
Future snapshots retain evidence with `state=unavailable` and omit calculations.
`researched_symbol_exposure` is zero if the symbol is absent from an otherwise usable
snapshot; it is not confused with a missing portfolio.

Import completeness, account reconciliation, option delta, fund look-through,
cross-currency exposure, covariance, VaR, and unrealized P&L are outside this model.

## Risk identification

Reports persist `risk_policy` (`research-v1`) and structured `risk_findings` with
stable rule codes, category, severity, message, observed value, threshold, and JSON
Pointer evidence references. Thresholds below are project research heuristics, not
personalized investment limits or an execution risk engine.

| Rule | Trigger | Severity |
| --- | --- | --- |
| Symbol concentration | Gross symbol value / equity > 25% | medium |
| Sector concentration | Gross sector value / equity > 40%, including Unknown | medium |
| Gross leverage | Gross invested value / equity > 1 | high |
| Nonpositive portfolio equity | Equity <= 0 | high |
| Short exposure / negative cash | Short magnitude > 0 / net cash < 0 | medium |
| High volatility | Annualized 20-return estimate > 40% | medium |
| Historical drawdown | Observed peak-to-trough decline <= -20% | medium |
| RSI extreme | RSI <= 30 or >= 70 | info |
| Revenue contraction / net loss / negative FCF | Respective metric < 0 | medium |
| Low current ratio | Current ratio < 1 | medium |
| High debt/equity | Debt/equity > 2 | medium |
| Nonpositive book equity | Book equity <= 0 | high |
| Near-term catalyst | Supplied event claim from now through seven days ahead | medium |
| Evidence warning / missing input | Existing warning / unavailable input | medium / info |

Missing metrics never imply zero risk. Future evidence does not trigger financial
or portfolio conclusions. Stale/sample warnings accompany descriptive findings
computed from such evidence. No composite safety score or trade authorization is
produced. Findings are sorted by severity, category, and code.

## Investment research reports

Schema 4 retains the prior fields and adds portfolio exposure, versioned risks,
`analysis_version=research-v2`, and a bounded `assessment` (`deterministic-v1`).
Versions 1–3 remain readable; legacy reports are not resynthesized on retrieval.
Storage still uses the existing JSON column, so this requires no table migration.

The assessment draws supporting/counter observations from revenue growth, net margin,
free cash flow, and SMA levels, with neutral return, portfolio, and news observations.
Each observation references computed fields in the persisted report. Existing
`bull_case`/`bear_case` lists mirror supporting/counter observations; these are neither
forecasts nor trade recommendations. Review questions and limitations are included.
Reports remain `partial`, with `investment_thesis` missing until valuation and
business-specific thesis/invalidation assumptions are supplied in a later milestone.

`GET /reports/{id}` returns JSON; `?format=markdown` downloads the same report as a
human-readable document. External headlines, source labels, and catalyst titles are
escaped before Markdown output. Export includes source timestamps, synthetic flags,
financial filing URLs, and news URLs. Original inputs and full precision remain in
JSON. No external text is executed or sent to an LLM.
