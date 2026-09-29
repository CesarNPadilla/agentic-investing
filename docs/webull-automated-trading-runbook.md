
# Webull Automated Trading Runbook

Status: API access is configured externally, and sandbox connectivity was verified by
the account owner on 2026-09-28. Credential values have not been read or shared here.
Sandbox test-order and production read-only CLIs are available; no live order execution is implemented.
Reviewed 2026-09-29.

## Current experimental phase override

Owner policy v0.1 now also requires proposal/entry/invalidation theses, daily research
and weekly portfolio review, advisory concentration warnings above 20%/30%, mandatory
audit, no auto-liquidation and no automatic rebalancing. VOO is the benchmark only.
Experimental loss remains separately UNSET. See the adopted policy documentation;
none of these declarations authorize use of the historical order walkthroughs below.

The current phase is **Investment Policy + Portfolio Intelligence**, paper/research only.
Production and automated trading are disabled; future live execution requires human approval.
Allowed securities are AAPL/MSFT/SPY, long-only, buy-only, cash-only, with no margin, options,
shorts, leverage, fractional or complex orders. The agent experimental capital limit is USD 160; it is not a cap on existing portfolio value. Daily loss remains UNSET; a kill switch is mandatory.
The [policy/reconciliation library](investment-policy-portfolio.md) evaluates
hypothetical proposals only. It does not enforce policy on the older standalone CLIs.
The walkthroughs below describe earlier tooling, not authorization to execute this phase.
Do not run sandbox or live orders as part of this work. Authenticated positions, settlement cash, buying power, paginated open orders and cash activities
are now normalized and persisted. Full share/settlement ledger coverage and atomic cutoffs
remain unavailable, so strict reconciliation still reports gaps. See ADR-013.

## Current State

This repository has no Webull order-execution integration. Phase 4 uses a local synthetic
account. Standalone sandbox tools can list test accounts, preview, explicitly submit,
check, or cancel test orders. A separate production read-only CLI retrieves account,
balance, position, and open-order responses. `WebullProductionBrokerReader` normalizes
accounts, cash, and positions to broker-neutral models. An opt-in authenticated `/broker`
API exposes those normalized reads; it is disabled by default and has no order methods.
Open orders remain available only as raw CLI responses. There is no live order route or
scheduler.
The Phase 5 policy endpoint records evidence qualification, but `/trading/automation/status`
continues to report `execution_available: false`. Do not use the existing synthetic
trading endpoints to place Webull orders; they do not connect to Webull.

You have already completed Webull API access setup and created
`C:\Users\cesar\AppData\Local\AgenticInvesting\webull.sandbox.env`, separate from the
production `webull.env`. Keep both files outside the repository and OneDrive. The sandbox
checker expects dotenv entries named `AIL_WEBULL_APP_KEY` and `AIL_WEBULL_APP_SECRET`. If the
variable names differ, change the names locally without sharing their values. Do not
paste the file or any credential values into chat.

The goal for the first iteration should be to prove the integration in Webull's test
environment, not to spend the $160. Webull documents a Trading API test endpoint and test
accounts. That is distinct from assuming the Webull app's paper-trading feature is
available through the API. Confirm the exact account and environment in the Webull portal
before sending any request.

## Webull Setup

1. Use the separate sandbox file and test account for development. Keep production
   credentials in `webull.env`; the sandbox checker does not load that file.
2. Start with Webull's test environment and a test account. The documented Trading API
   test host is `api.sandbox.webull.com`; production uses `api.webull.com`. Never test by
   pointing live credentials at the production host. Confirm the SDK returns a test
   account before testing any order call. Webull's API test account is not assumed to be
   the same thing as the paper-trading feature in the Webull app.
3. Use Webull's official Python SDK, following its current SDK documentation. The
   documented package is `webull-openapi-python-sdk`; verify the supported version and
   installation instructions before adding it to this project.
4. Keep both files outside this OneDrive-synchronized workspace, source control,
   notebooks, terminal transcripts, and Codex chat. Do not send the App Secret, account
   credentials, or access tokens to Codex.
5. Ask Webull support if the individual Trading API application is unavailable for your
   account. The separate **Connect API** is an OAuth product for third-party platforms;
   its published process involves an application, redirect URL, Webull approval, and
   sandbox testing. Do not assume it is interchangeable with an individual Trading API
   key.

Official references:

- [Trading API getting started](https://developer.webull.com/apis/docs/trade-api/getting-started)
- [Trading API overview](https://developer.webull.com/apis/docs/trade-api/overview)
- [Trading API accounts and buying power](https://developer.webull.com/apis/docs/trade-api/account)
- [Stock order parameters and lifecycle](https://developer.webull.com/apis/docs/trade-api/stock)
- [SDKs, environments, and test accounts](https://developer.webull.com/apis/docs/sdk)
- [Connect API overview](https://developer.webull.com/apis/docs/connect-api/about-connect-api)

## Verify Sandbox Access

From the repository root, install the optional Webull SDK support and run the read-only
check:

```powershell
& .\.venv\Scripts\python.exe -m pip install -e '.[webull]'
$sandboxEnv = Join-Path $env:LOCALAPPDATA 'AgenticInvesting\webull.sandbox.env'
& .\.venv\Scripts\python.exe scripts\check_webull_sandbox.py --env-file $sandboxEnv
```

The checker loads only `AIL_WEBULL_APP_KEY` and `AIL_WEBULL_APP_SECRET` from the specified file
and hard-codes `api.sandbox.webull.com`. It makes a read-only account-list request, prints
only whether sandbox access succeeded, and never prints the returned account data. It has
no order-placement code. Do not replace the sandbox filename with `webull.env`.

## Production Read-Only Access

The production CLI is deliberately separate from the sandbox tools and hard-codes
`api.webull.com`. It reads credentials only from the file passed with `--env-file`, and
supports account list, balance, positions, and one page of open orders. It exposes no
preview, place, replace, or cancel operation. Do not use the sandbox file here.

Use the production credential file only after confirming the Webull Trading API app is
approved. These calls contact the production API and may return private account data; keep
all output local:

```powershell
$productionEnv = Join-Path $env:LOCALAPPDATA 'AgenticInvesting\webull.env'
& .\.venv\Scripts\python.exe scripts\webull_production_read.py `
   --env-file $productionEnv accounts
$accountId = Read-Host 'Production account ID from the local account list'
& .\.venv\Scripts\python.exe scripts\webull_production_read.py `
   --env-file $productionEnv balance --account-id $accountId
& .\.venv\Scripts\python.exe scripts\webull_production_read.py `
   --env-file $productionEnv positions --account-id $accountId
& .\.venv\Scripts\python.exe scripts\webull_production_read.py `
   --env-file $productionEnv open-orders --account-id $accountId
```

The SDK stores authentication tokens under the configured token directory. Production uses
`%LOCALAPPDATA%\AgenticInvesting\webull-production-token`, separate from the sandbox
`conf\token.txt`; do not copy or delete the sandbox token when resolving production
authentication errors. If token verification expires, approve or renew production token
verification in the Webull app before retrying.

The open-orders command returns one API page. If the response includes a pagination key,
pass it as `--pagination-key` to retrieve the next page. These raw responses are not
normalized or connected to the application, and they do not enforce the proposed $160
account-wide exposure limit. No production order should be submitted through this tool.

To inspect response field names and JSON types without printing account values, add
`--shape-only` to any read command. For example:

```powershell
& .\.venv\Scripts\python.exe scripts\webull_production_read.py `
   --env-file $productionEnv balance --account-id $accountId --shape-only
& .\.venv\Scripts\python.exe scripts\webull_production_read.py `
   --env-file $productionEnv positions --account-id $accountId --shape-only
```

To expose normalized production reads in the local API, configure a unique bearer token
of at least 32 characters, distinct from both trading tokens. Keep Uvicorn bound to loopback;
the API returns private account data and does not add TLS or network-level access control.
These settings enable reads only, never order execution:

```powershell
$env:AIL_BROKER_READ_ENABLED = 'true'
$env:AIL_WEBULL_PRODUCTION_ENV_FILE = Join-Path $env:LOCALAPPDATA 'AgenticInvesting\webull.env'
$secureToken = Read-Host 'Enter the same 32+ character broker-read token from your password manager' -AsSecureString
$tokenPointer = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($secureToken)
try { $env:AIL_BROKER_READ_TOKEN = [Runtime.InteropServices.Marshal]::PtrToStringBSTR($tokenPointer) }
finally { [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($tokenPointer) }
& .\.venv\Scripts\python.exe -m uvicorn api.main:app --host 127.0.0.1 --port 8000
```

In another local terminal, make authenticated reads. Do not paste the token, account IDs,
or returned account data into chat:

```powershell
$headers = @{ Authorization = "Bearer $env:AIL_BROKER_READ_TOKEN" }
$secureToken = Read-Host 'Enter the same broker-read token' -AsSecureString
$tokenPointer = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($secureToken)
try { $env:AIL_BROKER_READ_TOKEN = [Runtime.InteropServices.Marshal]::PtrToStringBSTR($tokenPointer) }
finally { [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($tokenPointer) }
$headers = @{ Authorization = "Bearer $env:AIL_BROKER_READ_TOKEN" }
$accounts = Invoke-RestMethod 'http://127.0.0.1:8000/broker/accounts' -Headers $headers
$accounts
$accountId = Read-Host 'Account ID from the local response'
Invoke-RestMethod "http://127.0.0.1:8000/broker/accounts/$accountId/cash" -Headers $headers
Invoke-RestMethod "http://127.0.0.1:8000/broker/accounts/$accountId/positions" -Headers $headers
```

## Sandbox Order Walkthrough

The sandbox order tool lists sandbox accounts, previews a small buy-limit order, places it
only after an interactive confirmation, and supports status and cancellation requests.
It is hard-pinned to the sandbox API, permits only AAPL/MSFT/SPY buy orders with LIMIT/DAY/
CORE settings, and rejects any single order above USD 160. That cap is per order, not a
portfolio-wide exposure check. Do not use the tool with production credentials.

List accounts locally and choose the sandbox stock account ID. Keep this output private:

```powershell
$sandboxEnv = Join-Path $env:LOCALAPPDATA 'AgenticInvesting\webull.sandbox.env'
& .\.venv\Scripts\python.exe scripts\webull_sandbox_orders.py `
   --env-file $sandboxEnv accounts
$accountId = Read-Host 'Sandbox stock account ID'
```

The current policy forbids fractional quantities. Historical tooling accepts broader inputs;
it is not connected to this phase's evaluator. Preview does not place an
order. It displays the order and Webull preview response in your terminal:

```powershell
$symbol = Read-Host 'Allowed symbol (AAPL, MSFT, or SPY)'
$quantity = Read-Host 'Sandbox quantity'
$limitPrice = Read-Host 'Sandbox limit price'
$clientOrderId = [guid]::NewGuid().ToString()
& .\.venv\Scripts\python.exe scripts\webull_sandbox_orders.py `
   --env-file $sandboxEnv preview --account-id $accountId --symbol $symbol `
   --quantity $quantity --limit-price $limitPrice --client-order-id $clientOrderId
```

Review the preview output locally. To submit that exact sandbox order, use the same
values and ID. The command previews again and requires typing `PLACE SANDBOX ORDER`:

```powershell
& .\.venv\Scripts\python.exe scripts\webull_sandbox_orders.py `
   --env-file $sandboxEnv place --account-id $accountId --symbol $symbol `
   --quantity $quantity --limit-price $limitPrice --client-order-id $clientOrderId
```

Check its status and, if it remains open, request cancellation. Cancellation cannot undo
an order that has already filled in the sandbox:

```powershell
& .\.venv\Scripts\python.exe scripts\webull_sandbox_orders.py `
   --env-file $sandboxEnv status --account-id $accountId --client-order-id $clientOrderId
& .\.venv\Scripts\python.exe scripts\webull_sandbox_orders.py `
   --env-file $sandboxEnv cancel --account-id $accountId --client-order-id $clientOrderId
```

Order and preview responses can include account information. Keep terminal output private
and do not paste it here. The tool does not check buying power, positions, open-order
exposure, or daily loss; it must remain sandbox-only.

If Webull returns `OPENAPI_CAN_NOT_TRADING_FOR_FIXGW_NOT_READY_NIGHT` for a `CORE` order,
the sandbox order gateway is not accepting that order in the current session. Do not
change this restricted test tool to overnight trading. Check the order using the same
client order ID before considering another attempt during regular US market hours
(9:30 AM-4:00 PM Eastern, excluding market holidays). A successful preview does not
reserve funds or guarantee a later submission will be accepted. Avoid sharing raw SDK
error logs; they can contain request signatures and account identifiers.

## How Codex Would Handle It

The production read-only adapter normalizes accounts, cash, and positions, and authenticated
`/broker` routes can expose those models when explicitly enabled. The CLI can read raw
balances and open orders. The separate sandbox CLI can list accounts, preview a bounded
limit order, submit it after explicit interactive confirmation, and query or cancel it.
Account-wide buying-power checks, transaction reconciliation, scheduling, and production
order execution remain unimplemented.

Codex does not run continuously after this conversation and will not choose an investment
or strategy for you. The only order-submission path is the sandbox CLI, which previews
and then pauses for your typed confirmation. There is no production order-execution endpoint
or live order adapter. No live order should be sent unless you separately request that capability,
approve the exact live configuration, and confirm the specific order.

A future live mode must be a separate, explicit setting, defaulting off. Sandbox and
production endpoints and credentials must not be silently interchangeable. The local
kill switch must block new submissions, and you must also know how to cancel open orders
in Webull and revoke the API application credentials. A local kill switch cannot cancel
an order already accepted by Webull.

## Agent experimental capital rules (current)

`agent_experimental_capital_limit = 160` applies only to explicitly reviewed experimental
holdings and open orders. Existing portfolio value is unrestricted by that limit. All
holdings remain analyzable; only `new_purchase_allowlist` grants new BUY proposal permission.
The research universe is separate. Concentration warnings never cause a sale or rebalance.
Missing experimental attribution/loss decisions stay unset and block hypothetical approval.
See the [policy, read APIs, metrics and theses](investment-policy-portfolio.md) and
[ADR-013](adr-013.md). Authenticated API writes in that workflow save local notes/evidence
only; no broker order is placed, changed or cancelled.

The remaining trial sequence below describes future work requiring separate authorization.

## Implementation and Trial Sequence

1. **Confirm sandbox eligibility.** API access is already set up. Verify the test account
   and sandbox credentials in Webull's portal; keep production credentials private and
   unused during development.
2. **Complete read-only broker integration.** A production account/cash/position reader and
   authenticated API are implemented. Still add validated buying-power and open-order
   exposure models, data freshness checks, and reconciliation; test malformed responses,
   denied access, stale data, and network failures before considering order execution.
3. **Implement pre-trade checks.** Add the $160 account-wide cap, allowed-symbol list,
   limit/DAY/CORE-only validation, regular-session calendar, maximum daily loss, order
   preview, idempotent client order IDs, persistent audit records, order-status polling or
   streaming, cancel handling, and reconciliation. Any missing or stale account data must
   block submission.
4. **Exercise the test environment.** Use only Webull test credentials and its test
   account. Test preview, one test limit order, status updates, cancellation, duplicate
   retries, application restart, kill switch, and reconciliation. Verify that sandbox
   actions do not appear in the live account.
5. **Validate the strategy.** Register its criteria before evaluation; run holdout
   backtests and forward paper sessions. The repository's current Phase 5 default gate
   requires backtest excess return >= 5%, maximum drawdown <= 15%, and Sharpe >= 0.8, plus
   at least 60 sequential forward paper sessions with nonnegative return and maximum
   drawdown <= 10%. These are software gates, not a promise of profitability. Caller-
   declared data provenance is not independently certified by the current project.
6. **Review operational safeguards.** You review the code, the chosen strategy and
   limits, Webull's permissions, and the account shown by the API. Confirm the local and
   Webull-side emergency stop/cancel procedure. Keep the default live setting off.
7. **Only then consider a live pilot.** A live pilot requires Webull production API
   approval, explicit production credentials stored outside the repository, your explicit
   authorization, and a final confirmation of the exact symbol, side, quantity or cash
   amount, limit price, account, and maximum spend. Start with an order size you choose
   within the $160 ceiling. Watch it in Webull and be ready to cancel it manually.

## Your Decisions and Actions

You will need to:

- Verify that Webull's sandbox accepts the separate test credentials and returns access.
- Choose the strategy and permitted security or securities; Codex will not choose these
  for you.
- Confirm the $160 total cap, cash-only/no-margin rule, and a maximum daily loss.
- Decide whether Codex may only generate proposals or whether a separately authorized
  program may submit live orders later.
- Keep credentials in a secret manager outside OneDrive and enter them directly into your
  local environment. Never paste them into this chat.
- Review and authorize any live configuration and the exact first live order in Webull.
- Monitor positions and orders, stop the program when uncertain, cancel outstanding
  orders in Webull if needed, and revoke credentials if they may be exposed.

The production reader is wired into opt-in authenticated `/broker` routes, but account-wide
risk checks and qualifying forward-paper evidence are not complete. Do not enable live
trading. The next software steps are portfolio reconciliation, explicit strategy definition,
forward-paper validation, and independent production risk-control review, not order execution.
No $160 of real buying power will be moved or traded by the current repository. Sandbox
order responses stay in your terminal; do not share account IDs or output here.
