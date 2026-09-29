# Roadmap and phase gates

## Phase 1 - Research (current)

Completed foundation: local API, normalized quote and account models, provider boundary,
synthetic research workflow, structured persistent reports, deterministic data-quality
warnings, PostgreSQL container configuration, isolated development environment, tests.

Next milestones:
Alpaca IEX quotes and paginated daily close history are implemented, with 20/50-bar
moving averages, split-adjustment provenance, and explicit history-failure handling.
Fundamentals, news topic analysis, and dated catalyst tracking are implemented through
validated JSON evidence input, with provenance, deterministic calculations, persistence,
and missing/stale/future-data handling. Live fundamentals/news adapters remain pending.
Daily session completeness and dividend adjustments remain pending.

Technical indicators now include Wilder RSI14, MACD 12/26/9, Bollinger Bands20,
20-interval returns/annualized volatility, and observed-history drawdown. JSON equity
portfolio imports calculate cash, long/short, gross/net, and symbol/sector/account
exposure. Versioned deterministic risk findings and evidence-linked research
assessments are persisted with Markdown export. See [workflow](research-workflow.md).

1. Choose and evaluate a licensed market-data provider; preserve timestamp, source,
   corporate-action handling, rate limits, retries, and data-quality status.
2. Extend existing price/technical/fundamental/news analysis with live evidence adapters.
3. Extend implemented JSON equity portfolio imports with reconciliation and FX support.
4. Evaluate bounded LLM synthesis beyond the implemented deterministic research assessment;
   preserve evidence validation and external-text isolation tests.
5. Add database migrations, durable workers/scheduling, and run/failure audit records.
6. Validate Docker/PostgreSQL startup, persistence, backup/restore, and access controls.

Exit gate: useful source-grounded reports, missing/stale-data handling, reproducible
calculations, automated tests, and a reviewed deployment boundary. No trading.

## Phase 2 - Portfolio intelligence

Investment Policy v0.2 (ADR-014) adds monitoring-only sleeves, the approved position registry,
UNKNOWN original theses, persistent material events/review history and quarterly strategic
review requests. News can only request thesis review. Separate long-term/swing strategy
interfaces feed structured proposals into independent risk/human review; no new strategy
signals or execution are implemented. Swing controls remain UNSET until explicitly defined.
Timestamped analytics include Mag7, themes, speculative/swing exposure, verified correlations
and flow-adjusted VOO comparison when reliable evidence is supplied. Missing evidence remains
explicit. Required forward validation still includes 60 sequential non-synthetic sessions;
passing it cannot authorize production execution. See [ADR-014](adr-014.md).

ADR-013 separates real holdings, research universe and new-purchase permission. USD 160
now caps only explicitly attributed agent experimental capital, never existing portfolio
value. Authenticated Webull reads provide holdings/cash/open orders/cash activities;
persisted observations expose non-atomic and incomplete share/settlement-ledger evidence.
Whole-portfolio metrics, sourced classifications, informational concentration warnings and
revisioned position theses are implemented. Full broker share/settlement/corporate-action
coverage and reviewed experimental attribution remain gates. No auto-liquidation/rebalance.

Investment Policy + Portfolio Intelligence now provides an offline configurable policy,
complete-state import/reconciliation contract, account-wide metrics, deterministic hypothetical
risk evaluation and local durable evidence. Initial daily loss, freshness tolerance and day
boundary remain null and fail closed. No broker execution or strategy signals are added.
See [implementation and remaining decisions](investment-policy-portfolio.md). Read mappings
and pagination are implemented; coherent complete ledger evidence and production-grade
persistence/operations remain pending.

Persist accounts, positions, transactions, theses, purchase rationales, catalysts, target
allocations, risk assumptions, invalidation conditions, reviews, and performance history.
Gate: reconciled imports, reliable provenance, migrations, backups, and access controls.

## Phase 3 - Backtesting and paper trading

Implemented: versioned buy-and-hold/SMA strategies, validated historical inputs,
next-observation execution with fees/slippage, persisted local paper sessions,
benchmark/return/drawdown/trade/volatility/Sharpe metrics, and decision reasoning.
See [usage, conventions, limitations, and evaluation gate](backtesting-paper-trading.md).
Forward paper validation and provider-connected paper execution remain pending.

Version strategies and datasets. Measure return, benchmark, drawdown, win/loss, volatility,
risk-adjusted performance, and agent decisions. Control look-ahead and survivorship bias.
Gate: predefined acceptance criteria and demonstrated paper behavior. No live execution.

## Phase 4 - Human-approved trading

Agent -> trade proposal -> deterministic risk engine -> human approval -> broker adapter.
Implemented locally with a durable synthetic broker: immutable expiring proposals,
digest-bound approval, separate agent/human credentials, deterministic risk rechecks,
transactional idempotent execution, persistent kill switch, audit events, and ledger
reconciliation. See [Phase 4 workflow](human-approved-trading.md).
Production read-only account access is available through the separately authenticated API.
Live order integration and the production gate below remain pending.
Gate: broker/security review, isolated secrets, immutable approval details, audit logging,
idempotency, reconciliation, and kill switch tested end to end.

## Phase 5 - Limited automation

Implemented: human-registered, pre-evaluation strategy policies and a fail-closed
qualification check against persisted backtest and forward paper evidence. The default
gate requires backtest excess return >= 5%, maximum drawdown <= 15%, and Sharpe >= 0.8;
paper requires at least 60 sequential non-synthetic sessions, nonnegative return, and
maximum drawdown <= 10%. Evidence must be fully adjusted, match the registered strategy
and symbol, and paper observations must follow both policy registration and backtesting.
Policy caps cannot exceed USD 1,000 per order, USD 2,500 per position, USD 5,000 total
exposure, or USD 100 daily loss. Allowed symbols are restricted to AAPL/MSFT/SPY.

Automated order submission remains disabled: no execution endpoint or live execution
adapter exists, and no strategy currently has qualifying forward paper evidence. Market
hours, marked portfolio exposure, and daily-loss enforcement must be connected to a
trusted market-data and execution boundary before this gate can authorize automation.
See [Phase 5 readiness and limitations](human-approved-trading.md#phase-5-readiness-gate).
