# Agentic Investing Lab

Broker-neutral research with Phase 3 backtesting, local paper simulation, and opt-in
Phase 4 human-approved synthetic execution. No live order execution, default broker
connection, LLM calls, or credentials are included. An explicitly invoked Webull sandbox
test-order CLI is available; optional Alpaca market-data access is supported.

## Working location

`C:\Users\cesar\OneDrive\AI\agentic-investing` is the active project.
The earlier `C:\AI\agentic-investing` copy is no longer the working location.

## Implemented

- Human-approved trade proposals, deterministic risk checks, separate agent/human
  credentials, persistent kill switch, audit events, idempotent synthetic execution,
  and ledger reconciliation. See [Phase 4 workflow](docs/human-approved-trading.md).

- Versioned strategy backtests and persistent local paper sessions, with costs, benchmark
  comparison, drawdown, win/loss, volatility, Sharpe, and decision reasoning.
  See [Phase 3 workflow and runnable example](docs/backtesting-paper-trading.md).

- Webull sandbox-first setup, the $160 buying-power guardrail requirements, and the
  separation between Codex's implementation role and your trading authorization.
  See the [Webull automated trading runbook](docs/webull-automated-trading-runbook.md).

- An opt-in, separately authenticated production broker-read API for normalized account,
  cash, and position data. It is disabled by default and cannot place or cancel orders.

- FastAPI endpoints: health, database readiness, create research report, retrieve report.
- Provider-independent research orchestrator with Pydantic JSON outputs.
- Market-data protocol and explicitly synthetic AAPL fixture (100 USD, dated 2026-01-01).
- UUID reports with source, data timestamp, generation timestamp, schema version, and missing data.
- Deterministic sample/stale/future-data warnings; decimal monetary values.
- SQLAlchemy report persistence: PostgreSQL in Docker, SQLite for local development/tests.
- Broker-neutral read contract wired to opt-in authenticated production account reads; the
  text-only LLM contract is not connected at runtime.
- Research-only configuration validation; unknown providers and live/paper modes are rejected.

Fundamental metrics, news topics, and dated catalysts accept optional validated JSON
evidence with provenance. See [the input contract and runnable example](docs/research-evidence.md).
Technical analysis includes moving averages, RSI, MACD, Bollinger Bands, returns,
volatility, and drawdown. JSON portfolio snapshots add symbol/sector/account exposure.
Versioned risk rules and evidence-linked research assessments are included, with
Markdown report downloads. See [the full workflow and example](docs/research-workflow.md).
Valuation and business-specific investment theses remain pending. Reports return
`partial` and identify missing inputs rather than fabricating analysis. Only AAPL is
available from the sample provider. The optional Alpaca adapter fetches real IEX
last trades and up to 180 calendar days of split-adjusted daily closes.

## Local startup (PowerShell)

Keep the environment outside OneDrive. The following environment has been created during setup:

```powershell
Set-Location 'C:\Users\cesar\OneDrive\AI\agentic-investing'
$researchPython = 'C:\Users\cesar\.codex\venvs\agentic-investing\Scripts\python.exe'
# On a new machine: python -m venv 'C:\Users\cesar\.codex\venvs\agentic-investing'
& $researchPython -m pip install -e '.[dev]'
# Keep the active local database outside the sync folder.
$dataDirectory = Join-Path $env:LOCALAPPDATA 'AgenticInvesting'
New-Item -ItemType Directory -Path $dataDirectory -Force | Out-Null
$env:AIL_DATABASE_URL = 'sqlite:///' + (Join-Path $dataDirectory 'research.db').Replace('\', '/')
& $researchPython -m uvicorn api.main:app --host 127.0.0.1 --port 8000
```

Open http://127.0.0.1:8000/docs. In a second terminal:

```powershell
$report = Invoke-RestMethod -Method Post 'http://127.0.0.1:8000/research/AAPL'
$report
Invoke-RestMethod "http://127.0.0.1:8000/reports/$($report.id)"
```

`GET /health` is liveness; `GET /ready` checks database connectivity. Report creation returns
201, unsupported symbols return 404, invalid inputs return 422, and provider/storage
unavailability returns 503. Database initialization failure prevents startup.

Research endpoints have no authentication; opt-in trading endpoints require role-specific
bearer credentials. The API must remain bound to loopback. Review authentication,
TLS, authorization, secrets storage, backups, and network isolation before shared deployment.
Never add personal portfolios or secrets to sample fixtures. `.gitignore` does not prevent
OneDrive synchronization; put real secrets and active databases outside the synced tree.

## Docker + PostgreSQL

This machine's development password is stored outside OneDrive in
`%LOCALAPPDATA%\AgenticInvesting\docker.env`. With Docker Desktop running, use:

```powershell
$dockerEnvPath = Join-Path $env:LOCALAPPDATA 'AgenticInvesting\docker.env'
docker compose --env-file $dockerEnvPath up --build -d
docker compose --env-file $dockerEnvPath ps
Invoke-RestMethod 'http://127.0.0.1:8000/ready'
# Stop services while keeping the database volume:
docker compose --env-file $dockerEnvPath down
```

Stop any local Uvicorn server on port 8000 before starting the Docker API.
Keep the password file for future starts; changing it does not reset the password
in an existing PostgreSQL volume. Open http://127.0.0.1:8000/docs to try the API.

For a fresh setup on another machine:

Docker must be installed separately. In the project directory:

```powershell
# Only create .env if it does not already exist.
if (-not (Test-Path .env)) { Copy-Item .env.example .env }
# Set POSTGRES_PASSWORD to a local development database password in .env.
docker compose up --build
```

Compose exposes the API only on 127.0.0.1:8000, does not publish the database port, and stores
PostgreSQL data in a named Docker volume. This is a local development configuration.
The password is for the local database, not a broker. Prefer a shell environment variable
for POSTGRES_PASSWORD to avoid syncing even a development secret. The container entrypoint
encodes reserved password characters safely. Use `docker compose down` to stop services;
the named database volume persists.

## Checks

### Alpaca IEX market data

The optional Alpaca adapter uses only the market-data API. Save paper-account
credentials as `AIL_ALPACA_API_KEY` and `AIL_ALPACA_API_SECRET` in
`%LOCALAPPDATA%\AgenticInvesting\alpaca.env`, outside OneDrive. Start with:

```powershell
docker compose --env-file "$env:LOCALAPPDATA\AgenticInvesting\docker.env" --env-file "$env:LOCALAPPDATA\AgenticInvesting\alpaca.env" -f docker-compose.yml -f docker-compose.alpaca.yml up --build -d
```

This override selects Alpaca; the base Compose file retains sample defaults.
Prices are USD last trades from IEX only, with the provider's observation time.
They are not consolidated quotes or executable prices. Reports now include daily
close history and 20/50-bar simple moving averages when enough data is available.
Today's New York session is excluded; bars are split-adjusted, not dividend-adjusted.
IEX session completeness is not exchange-calendar verified. These descriptive
indicators are not buy/sell recommendations. History failures retain the quote and
mark history/technicals missing. New reports use schema version 4; version 1, 2, and 3 reports
remain readable. Live fundamentals/news providers and investment theses remain pending.
Alpaca requests have a
10-second HTTP timeout and no automatic retries; quota/auth/provider failures
return 503 without falling back to synthetic data. No trading API is connected.

### Automated checks

```powershell
& $researchPython -m pytest -q
& $researchPython -m ruff check .
```

Dependencies are bounded in `pyproject.toml`; `requirements-tested.txt` records the resolved
Windows/Python test environment, not a universal cross-platform lock.

## Boundaries and next steps

The application calls market-data interfaces and a report repository by default. When
explicitly enabled, authenticated `/broker` routes use the read-only production broker
contract in `integrations/brokers/base.py`; this does not enable order execution.
Order submission and cancellation are intentionally deferred to Phase 4's separately
reviewed execution service. Agents cannot be given execution capabilities through settings.
The current data-quality checks are not a complete portfolio or trade risk engine.

Workers and scheduler packages remain reserved. The initial
API is synchronous; durable job scheduling is a later milestone. Schema bootstrap uses
`create_all`; introduce migrations before changing the stored schema.

See [architecture](docs/architecture.md), [decision log](docs/decisions.md), and
[roadmap](docs/roadmap.md).
#   a g e n t i c - i n v e s t i n g  
 