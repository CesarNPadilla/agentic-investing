# Historical strategy research path

Phase v0.5 adds an independent [corporate-action ledger](corporate-action-ledger-design.md)
and [adjustment methodology](historical-adjustment-methodology.md). A bounded
read-only snapshot can be reproduced with `python -m experiment_lab.corporate_action_snapshot`
using the external Alpaca env file, the fixed eleven symbols, and dates ending
no later than 2025-12-31. Store output outside the repo; the command refuses
to replace an existing snapshot. `EXPLORATORY_RESEARCH` output may illustrate
split arithmetic and dividend accounting with declared assumptions, but remains
nonqualifying. `QUALIFYING_VALIDATION` requires independently evidenced complete
events, historical publication classification for signals, reproducible raw-to-
adjusted accounting, VOO methodology alignment, and every frozen research gate.
No exploratory output is promoted automatically; neither mode authorizes trading.
See [provider review](data-provider-qualification-corporate-actions.md),
[VOO status](voo-benchmark-qualification.md), and [review 005](historical-evidence-review-005.md).

`docs/examples/strategy-experiment-lab-v01/results.json` is a **synthetic software
fixture**. Its zero-trade rows are not empirical performance. An Alpaca-price
diagnostic is documented in
[historical-research-review-001.md](historical-research-review-001.md); no
qualifying historical validation results for either strategy have been produced.

Review 002 adds a separate `HistoricalPriceProvider`,
`HistoricalFundamentalProvider`, `CorporateActionProvider`, and
`TradingCalendarProvider`, plus `HistoricalKnowledgeBoundary`. Its live FMP
qualification failed HTTP 402; current-vintage FMP values must not be treated
as historical knowledge. See [provider qualification](data-provider-qualification-fmp.md),
[review 002](historical-research-review-002.md), and the external immutable
qualification audit. The 2026 OOS interval stays closed.

Review 003 uses SEC EDGAR as the primary historical-fundamental candidate.
Its accession-level reconstruction is conditional because today's companyfacts
and the filing acceptance timestamp do not prove the original public value
vintage. The adapter rejects 2026 requests and does not feed unqualified facts
to either strategy. See [SEC qualification](data-provider-qualification-sec-edgar.md)
and [review 003](historical-research-review-003.md).

To acquire only the development/validation raw price snapshot, use
`python -m experiment_lab.raw_price_fetch` with an external Alpaca env file,
fixed symbols, and an end date no later than 2025-12-31. The command refuses
an existing output or any reserved 2026 date. Raw bars have no inferred
corporate-action vintage; action observations are stored in their own type.

The new `experiment_lab.historical_data.HistoricalResearchProvider` contract accepts
timestamped, fully adjusted OHLCV, exact exchange session closes, and publication-
timestamped fundamental observations. `JsonHistoricalResearchProvider` reads a
provider export without inventing observation times or provenance. The read-only
Alpaca adapter fetches `adjustment=all` daily bars and uses Alpaca's calendar to
map the daily date label to the actual session close, including early closes. It
marks point-in-time adjustment history, complete corporate actions, and historical
fundamentals **unverified**. Its current-vintage download can produce explicitly
retrospective candidate statistics, but fails the historical quality and
zero-look-ahead gates. Alpaca's `asof` parameter maps historical symbols; it is
not evidence that today's adjusted values were available on an earlier decision
date. No credential or entitlement is shipped with this repository.

`ResearchRules` supplies fixed, research-only candidate rules. Long-term entry
requires reported revenue growth at least 8%, positive free cash flow, net debt
to EBITDA at most 3, free cash flow yield at least 2%, and price above its 200
session average. It reviews every 21 sessions and models an exit if those
fundamental gates deteriorate. Swing entry requires price above SMA200, SMA50
above SMA200, RSI14 between 50 and 75, and volume above the preceding 20-session
mean. Its counterfactual exits are a two-ATR stop, trend failure, or a 20-session
holding limit. Each signal fills, if possible, at the **next** session close with
5 bps adverse slippage, 2 bps full spread, and a $0.10 commission. Research
capital is $100,000 with 10% target entry notional; the separate $160 case uses
whole shares and available cash only. No leverage or fractional shares are used.
These are exploratory proxy rules, not approved Investment Policy parameters or
production authorization. The quality-growth proxy is not a replacement for
source-linked qualitative business, valuation, thesis, and portfolio review.

The read-only Alpaca acquisition command accepts a credential file outside the
repository. It never prints or copies the key or secret. Its output is real
market history with explicit vintage limitations; it cannot satisfy a qualifying
validation gate by itself:

```powershell
python -m experiment_lab.historical_fetch `
  --env-file 'C:\Users\cesar\AppData\Local\AgenticInvesting\alpaca.env' `
  --output path/to/alpaca-history.json --dataset-id alpaca-study-001 `
  --symbols AAPL,MSFT,NVDA,AMZN,GOOGL,GOOG,META,TSLA,PLTR,INTC,VOO `
  --start 2022-06-10 --end 2026-09-29 --feed iex
```

The frozen default validation gates are: at least 126 observations and five
candidate trade sides **per strategy** in normalized-capital validation, maximum
25% drawdown, maximum 3x turnover, no accepted data-quality findings, zero
look-ahead violations, and zero policy bypasses. The $160 case has its own gate
report, because whole-share affordability can differ sharply. The three
development-only sensitivity probes are SMA50→55, RSI lower 50→52, and ATR
multiple 2→2.2. No probe changes the frozen baseline. A validation failure
prevents the out-of-sample stage from running or writing any OOS result.

To use a genuine provider export, create a `HistoricalResearchDataset` JSON with
the typed fields in `experiment_lab/historical_data.py`. Every bar needs its
symbol, exact session close, actual availability time, and adjustment vintage
time. Fundamental points need period end, publication and availability times,
source ID, and the four named metrics. The provider must attest exchange-calendar,
corporate-action, adjustment-vintage, and fundamental-vintage completeness. The
adapter rejects synthetic input and duplicate/off-calendar bars. It does not
accept a current-vintage adjusted download relabeled as historical point-in-time
evidence. A source able to supply certified historical vintages can implement the
same `load(dataset_id, version)` protocol.

Create the plan **before any performance run** with fixed, non-overlapping date
windows and a fixed universe; review its rules and gates, then run it once:

```powershell
python -m experiment_lab.historical_plan --dataset path/to/provider-export.json `
  --output path/to/frozen-plan.json --plan-id historical-study-001 `
  --symbols AAPL,MSFT,NVDA,AMZN,GOOGL,META,TSLA,PLTR,INTC `
  --development-start YYYY-MM-DD --development-end YYYY-MM-DD `
  --validation-start YYYY-MM-DD --validation-end YYYY-MM-DD `
  --oos-start YYYY-MM-DD --oos-end YYYY-MM-DD

python -m experiment_lab.historical_run --plan path/to/frozen-plan.json `
  --dataset path/to/provider-export.json --output path/to/empty-output `
  --registry path/to/persistent-historical-registry.sqlite
```

The registry reserves OOS symbol/date exposure before calculation. Reusing the
plan or overlapping an exposed OOS interval is rejected, including after a
failed run. Development results and sensitivity are written first; validation
results and gates next; OOS remains sealed even if validation passes, pending
a separate human architecture decision and release implementation. The candidate
ledger explicitly records `NOT_SUBMITTED_RESEARCH_ONLY`. It cannot submit a
`TradeProposal` or call a broker. Candidate statistics **cannot** by themselves
make either strategy paper eligible. The existing policy-approved backtest and
human-review gates remain separate. The 60-session forward-paper counter stays
at zero; paper and production execution remain disabled.

Sources for adapter semantics: [Alpaca historical bars](https://docs.alpaca.markets/us/reference/stockbars),
[Alpaca market calendar](https://docs.alpaca.markets/us/reference/legacycalendar),
[Alpaca corporate actions](https://docs.alpaca.markets/us/reference/corporateactions-1).
