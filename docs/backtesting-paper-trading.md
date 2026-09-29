# Phase 3: backtesting and local paper trading

The API now runs deterministic, versioned `buy_and_hold` and `sma` strategies.
Both are long-only, fully invested or cash, with fractional shares. SMA holds cash
until its slow window is available, then targets long when fast SMA > slow SMA.
Equal averages target cash. Strategy version `1` and engine `simulation-v1` are stored.

## Run a backtest

Generate a synthetic request and send it to the running API:

```powershell
$researchPython = 'C:\Users\cesar\.codex\venvs\agentic-investing\Scripts\python.exe'
$body = (& $researchPython docs/examples/build_backtest.py) -join "`n"
$run = Invoke-RestMethod -Method Post 'http://127.0.0.1:8000/backtests' `
    -ContentType 'application/json' -Body $body
$run.metrics
$run.decisions | Select-Object -Last 5
Invoke-RestMethod "http://127.0.0.1:8000/simulations/$($run.id)"
```

Requests require `history` and `benchmark`, each following the existing history
evidence contract: symbol, source, adjustment, synthetic flag, and dated closes.
Timestamps must match exactly, and adjustment conventions must agree. Only prior
New York calendar days are accepted. Maximum 5,000 observations. USD inputs are
assumed; the engine does not convert currencies or verify exchange calendars.
Fees and adverse slippage are independently configurable in basis points (0–100).

## Advance a paper session

`POST /paper-sessions` accepts the same request with exactly one paired observation.
This starts with cash and records the first pending decision. For each subsequent
completed daily observation, call `POST /paper-sessions/{id}/bars`:

```json
{
  "expected_revision": 0,
  "bar": {"timestamp": "2020-01-02T21:00:00Z", "close": "101"},
  "benchmark_bar": {"timestamp": "2020-01-02T21:00:00Z", "close": "100.5"}
}
```

Use the returned revision for the next request. Duplicate/stale revision writes
return 409; invalid dates/alignment return 422 without changing state. On an
uncertain network result, retrieve the session before retrying. A database
compare-and-swap protects concurrent writes. Sessions survive application restarts.
The stored history is replayed deterministically on each append, retaining every
decision, fill, and equity point. This is a local paper ledger fed by imported bars,
not a broker paper account or scheduled market-data feed. Historical replay is
supported but is not evidence of forward paper performance.

## Execution and measurement conventions

Signals at close t fill at the next supplied close t+1. The simulator never fills
using the price that generated the signal. Buy quantity includes the proportional
fee in its cash budget; sells deduct fees. Slippage increases buy prices and reduces
sell prices. Positions remain open at the end; the final signal stays pending.
No same-close execution, forced liquidation, borrowing, shorts, or live orders exist.

| Metric | Convention |
| --- | --- |
| Total return | Final marked equity / starting cash − 1, including costs |
| Benchmark return | Last / first benchmark close − 1, frictionless |
| Excess return | Strategy return − benchmark return |
| Maximum drawdown | Most negative equity / running peak − 1 |
| Volatility | Sample standard deviation of adjacent equity returns × sqrt(252) |
| Sharpe ratio | Mean daily return / sample standard deviation × sqrt(252), zero risk-free rate |
| Wins/losses/breakeven | Positive/negative/zero net P&L on completed round trips |
| Win rate | Wins / completed trades; null without completed trades |
| Profit factor | Sum of winning P&L / magnitude of losing P&L; null without losses |
| Realized/unrealized P&L | Closed net trade P&L / marked open position minus entry cost |

Volatility needs at least two return observations; Sharpe is null when variance
is zero or insufficient. Fractions are not percentages. Monetary accounting uses
Decimal; statistical outputs use floating point. Open trades do not enter win rate.
Benchmark starts at the first close while strategy execution begins later, so
excess return includes initial cash drag and asymmetric costs.

Every decision records agent identifier, strategy version, timestamp, observed
window size, SMA values, target, action, and deterministic reasoning. No LLM is
used. Persisted inputs include all source metadata. `dataset_hash` is SHA-256 of
the normalized complete request, including strategy and cost settings; it is a
reproducibility fingerprint, not an external data certification. Retrieval does
not recalculate reports. Storage adds a separate `simulation_runs` table through
the existing bootstrap mechanism; a production migration system remains pending.

## Evaluation gate

Before treating any strategy as validated, record its evaluation period, benchmark,
cost assumptions, holdout period, minimum closed-trade count, acceptable drawdown,
and required net/excess return and Sharpe thresholds **before** running evaluation.
Then evaluate untouched holdout data and collect forward paper observations with
the same settings. There are deliberately no universal profitability thresholds
or automatic promotion to live trading. No strategy has passed this gate merely
because the software tests pass.

Phase 5 adds a human-registered qualification policy before evaluation. Its fixed default
thresholds are backtest excess return >= 5%, maximum drawdown <= 15%, Sharpe >= 0.8, and
at least 60 sequential non-synthetic forward paper sessions with nonnegative return and
maximum drawdown <= 10%. The persisted evidence must match the registered strategy and
symbol; paper observations must postdate both policy registration and the backtest period.
This is a qualification check only; it does not enable order submission.

Selected securities can carry survivorship bias. Data revisions and tuning against
the test set can introduce additional bias. Gaps, stale inputs, liquidity, spreads,
taxes, settlement, separate dividend cash flows, and corporate actions are not
fully modeled. Raw/split-only and synthetic inputs produce explicit warnings;
fully adjusted series represent synthetic units rather than executable share lots.
Provider-connected paper execution, reconciliation, automated scheduling, immutable
external audit storage, and live approval workflows remain future work.
