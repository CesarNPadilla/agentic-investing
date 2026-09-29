# Phase 4 — Human-approved trading

Implemented flow: agent → immutable trade proposal → deterministic risk engine →
human approval → execution-time risk check → synthetic broker.

This is a local end-to-end implementation, not live broker execution. The synthetic
account starts with 10,000 USD and no positions. It fills immediately at the requested
limit price, without market data, fees, liquidity, or trading-session modeling. These
fills must not be used to evaluate strategy performance. Phase 3 remains separate.

## Start the service

Use the existing README environment and database setup. Generate two distinct random
credentials of at least 32 characters through your secret manager and set these
environment variables before starting Uvicorn:

```powershell
$env:AIL_TRADING_ENABLED = 'true'
# Set AIL_TRADING_AGENT_TOKEN and AIL_TRADING_APPROVAL_TOKEN securely.
# Do not put real credentials in source control or share the human token with agents.
& $researchPython -m uvicorn api.main:app --host 127.0.0.1 --port 8000
```

Trading is disabled by default; its routes are absent unless enabled. Enabling it
requires distinct credentials. `AIL_MODE` remains `research` for the research service;
`/health` separately reports synthetic execution and `live_trading_enabled: false`.
The durable kill switch starts **enabled** on the first startup. Restarts preserve it.
Tables are added with the existing bootstrap mechanism; existing research data is retained.

Bearer tokens provide a local role boundary, not proof of a person's presence. Keep
the approval token outside the agent's environment and tools. Run on loopback only;
other research endpoints still have no authentication. Production isolation requires
a separate approval service/identity provider, TLS, and individual reviewer identities.

## Agent: create a proposal

After a human enables the synthetic workflow (see below), run in the agent client:

```powershell
$base = 'http://127.0.0.1:8000'
$agentHeaders = @{ Authorization = "Bearer $env:AIL_TRADING_AGENT_TOKEN" }
$body = @{
    account_id = 'synthetic-phase4'
    symbol = 'AAPL'
    side = 'buy'
    quantity = '2'
    limit_price = '100.00'
    order_type = 'limit'
    time_in_force = 'day'
    strategy = 'reviewed-example-v1'
    rationale = 'Synthetic approval workflow exercise'
    request_id = [guid]::NewGuid().ToString()
} | ConvertTo-Json
$proposal = Invoke-RestMethod -Method Post "$base/trading/proposals" `
    -Headers $agentHeaders -ContentType 'application/json' -Body $body
$proposal | ConvertTo-Json -Depth 10
```

Proposals are immutable, expire after 15 minutes, and carry a SHA-256 digest binding
the ID, order details, broker, and timestamps. Reusing `request_id` with the same
payload returns the existing proposal; different details return 409. Amendments require
a new request ID and human approval. The agent can call this endpoint from its own
orchestration; research reports do not automatically generate or execute trades.

Risk policy `synthetic-risk-v1`: only AAPL/MSFT/SPY, USD synthetic account, limit/day
orders, maximum 1,000 USD per order, sufficient cash, no shorts, and maximum 2,500 USD
per symbol valued at the proposed limit price. This is not a marked-to-market exposure
limit. Policy and broker selection are server-owned, not proposal inputs.

## Human: enable, review, approve or reject

Use a separate human-controlled client with the approval credential. Before creating
the first proposal, explicitly disable the kill switch:

```powershell
$base = 'http://127.0.0.1:8000'
$humanHeaders = @{ Authorization = "Bearer $env:AIL_TRADING_APPROVAL_TOKEN" }
Invoke-RestMethod -Method Put "$base/trading/kill-switch" -Headers $humanHeaders `
    -ContentType 'application/json' -Body '{"enabled":false}'
```

Copy the proposal ID into the human client, retrieve it, and inspect all order details,
rationale, risk results, broker, and expiration before approving:

```powershell
$proposalId = Read-Host 'Proposal ID to review'
$review = Invoke-RestMethod "$base/trading/proposals/$proposalId" -Headers $humanHeaders
$review | ConvertTo-Json -Depth 10
# Run only after your review:
Invoke-RestMethod -Method Post "$base/trading/proposals/$proposalId/approve" `
    -Headers $humanHeaders -ContentType 'application/json' `
    -Body (@{ digest = $review.digest } | ConvertTo-Json)
# Alternatively, reject:
# Invoke-RestMethod -Method Post "$base/trading/proposals/$proposalId/reject" -Headers $humanHeaders
```

Approval accepts only the digest, never edited order details. The agent credential
cannot approve, reject, or change the kill switch. A blocked, rejected, or expired
proposal cannot be revived; submit a new proposal for review.

## Agent: execute the approved order

```powershell
Invoke-RestMethod -Method Post "$base/trading/proposals/$($proposal.id)/execute" `
    -Headers $agentHeaders
Invoke-RestMethod "$base/trading/account" -Headers $agentHeaders
```

Execution requires persisted human approval and reruns risk using current account
state. Approval reserves no funds. Changed balances or exposure can block execution.
Repeated/concurrent execution requests return the same stored receipt without another
fill. Check the returned `status`; expiry or risk failure returns the resulting state.
Invalid transitions return 409, missing credentials 401, invalid input 422, and storage
failure 503. No `/orders` bypass exists.

## Stop and reconcile

```powershell
Invoke-RestMethod -Method Put "$base/trading/kill-switch" -Headers $humanHeaders `
    -ContentType 'application/json' -Body '{"enabled":true}'
Invoke-RestMethod -Method Post "$base/trading/reconcile" -Headers $humanHeaders
Invoke-RestMethod "$base/trading/audit" -Headers $humanHeaders
```

Mutations serialize through a database control row across processes. Whichever
transaction acquires that row first takes effect first; a kill switch cannot undo a
completed fill. Fill, account update, and audit event commit atomically. Reconciliation
rebuilds the synthetic account from stored receipts, checks approval linkage, and
enables the kill switch on mismatch. Audit events are append-only through the API,
but are not tamper-proof against database administrators. Failed authentication and
invalid requests are not persisted in the trade audit.

## Remaining live-broker gate

No live adapter or network submission is implemented or enabled. Before introducing
one, complete broker/security review, isolated broker secrets and approval identity,
versioned migrations, backups, tamper-resistant audit retention, broker-side idempotency,
durable submission/outbox and unknown-outcome recovery, external order/fill reconciliation,
cancel/partial-fill handling, and independent market/session/exposure controls.
The synthetic transaction cannot be reused as a distributed network-order transaction.
PostgreSQL locking behavior and operational deployment still need integration validation.

## Phase 5 readiness gate

Automation policy is separate from Phase 4 human-approved orders. Register the strategy
policy before running either evaluation, using `PUT /trading/automation/policy` with the
human credential. The default policy is fixed to these qualification criteria:

- Backtest excess return >= 5%, maximum drawdown <= 15%, and Sharpe ratio >= 0.8.
- At least 60 sequential forward paper sessions, with nonnegative return and maximum
    drawdown <= 10%.
- Backtest and paper evidence use the same registered strategy and allowed symbol, are
    fully adjusted and non-synthetic, and paper observations begin after policy registration
    and the backtest period.

Then submit persisted run IDs to `POST /trading/automation/qualification`. The result and
the linked evidence IDs are audited. `GET /trading/automation/status` reports the stored
policy and qualification. Policies cap order value at USD 1,000, single-position value at
USD 2,500, total exposure at USD 5,000, and daily loss at USD 100; symbols are limited to
AAPL, MSFT, and SPY. The existing proposal contract accepts only limit/day orders.

Qualification is not authorization to trade. There is deliberately no automation-enable
or automated-order endpoint, and status always reports `execution_available: false`.
No strategy currently has qualifying forward paper evidence. Trusted market-hour checks,
mark-to-market exposure and daily-loss accounting, a scheduler/strategy signal source, and
a reviewed execution adapter must be implemented before automated submission is considered.
The typed limit/day, idempotency-keyed adapter contract is in
[`integrations/brokers/orders.py`](../integrations/brokers/orders.py); it has no network-backed
implementation. Evidence provenance is caller-declared and is not independently certified.
The synthetic Phase 4 broker and imported historical replay cannot establish those controls.
