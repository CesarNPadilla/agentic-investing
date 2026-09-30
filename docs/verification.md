# Verification - 2026-09-28

## Backtesting & Strategy Validation v0.1 — 2026-09-30

- Full suite: **419 passed, 0 failed**, including 47 new backtesting cases.
- Repository Ruff lint passed; all 14 changed/new Python files pass Ruff formatting.
- Tests cover cutoff isolation for prices/fundamentals/news/vintages, nested future-source
  rejection, shared strategy/risk replay, calendar gaps, split/reverse-split/dividend
  accounting and reconciliation, same-date benchmark bases, costs/slippage/cash/limits,
  capital modes, unapproved securities, long-only/fraction mechanics, swing forward gate,
  metrics, cadence, immutable registry, replay equality, bias/holdout/validation gates,
  prompt-injection inertness and broker method/network sentinels.
- `python -B -m backtesting.demo` completed using synthetic fixtures only. Saved output:
  [demo result](examples/backtesting-demo-result.json). Validation FAIL / NOT_ELIGIBLE;
  zero forward-paper credit. This establishes software behavior, not investment performance.
- One pre-existing Starlette/httpx deprecation warning remains. No dependency upgrades,
  credentials, private databases or broker connectivity were needed. Temporary SQLite;
  PostgreSQL migrations/concurrency/restore remain unverified.

## Long-Term Research Agent v0.1 — 2026-09-29

- Full suite: 311 passed, including 29 new long-term research cases.
- Repository Ruff lint passed; all eight new Python files passed formatting checks.
- Coverage includes provider/source/freshness validation, research transitions, portfolio
  context, cost-basis independence, news review/deduplication, quarterly cycles, atomic
  thesis rollback, issuer aliases and the absence of execution capabilities.
- Existing Starlette/httpx deprecation warning remains. No dependencies changed.
- Temporary SQLite and synthetic test data only. No broker, live provider, credential,
  production order, deployment or commit action occurred. PostgreSQL operational validation
  remains outstanding. See [completion report](long-term-research-completion.md).

Active source: C:/Users/cesar/OneDrive/AI/agentic-investing
Environment: C:/Users/cesar/.codex/venvs/agentic-investing (Python 3.14.7)

## Research workflow extension verification

- 97 tests passed after adding technical indicators, JSON portfolio exposure,
  versioned risk findings, deterministic research assessments, and Markdown export.
- Numeric checks cover Wilder RSI seed/smoothing, trend/flat MACD, population
  Bollinger variance, sample-return volatility, drawdown, indicator warm-up, and
  long/short gross-versus-net portfolio aggregation.
- Boundary checks cover invalid currency/positions, future/stale evidence, threshold
  equality, symbol mismatch, JSON input precedence, and escaped external Markdown.
- Integration checks cover source-reference resolution, the complete documented
  example, API report persistence across restarts, and older report schemas.
- Repository-wide Ruff checks passed. The existing Starlette/httpx deprecation
  warning remains; dependency versions were not changed by this extension.
- Checks used synthetic evidence and temporary SQLite databases. Docker/PostgreSQL
  deployment and live portfolio/news/financial adapters were not exercised.

## Original foundation verification

- Editable installation succeeded.
- 16 tests passed: report creation/retrieval across application restarts, decimal
  preservation, sample labeling, provider replacement/failure/mismatch, input validation,
  rejected live/paper modes, absent order routes, and timestamp/data-quality checks.
- Ruff checks passed. Dependency consistency check passed.
- One upstream deprecation warning: Starlette's TestClient currently warns about httpx;
  this does not affect the passing tests or application runtime.
- Docker executable unavailable; image build and PostgreSQL runtime unverified.
- Tests use temporary SQLite storage outside OneDrive, not a real portfolio.
- No persistent API server was started, and no external data or broker services were called.

The original C:/AI/agentic-investing copy was retained. Continue development only in the
active OneDrive source directory. An existing .venv in that directory was not used; the
verified environment is outside OneDrive. Pytest's cache is disabled to avoid a OneDrive
cache-directory rename error observed during the first run.
# Phase 4 verification

`tests/test_trading.py` covers credential separation, immutable approval inputs,
execution without approval, idempotency conflicts, risk rejection, input validation,
kill switch after approval, restart persistence, concurrent duplicate execution,
changed exposure, expiry/rejection, sell accounting, reconciliation mismatches, and
atomic rollback when audit persistence fails. Tests use SQLite and the synthetic
broker; real broker and PostgreSQL deployment validation remain pending.
