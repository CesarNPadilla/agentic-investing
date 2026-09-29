# Investment policy and portfolio intelligence

Owner policy revision: **0.1**. Current software schemas: `investment-policy-v3`,
`portfolio-state-v2`, `investment-risk-v3`. This replaces the earlier whole-portfolio
USD 160 interpretation. Production/automated execution and automatic rebalancing remain
disabled. No broker submission, cancellation or modification is added.

## Three separate scopes

| Concept | Meaning | Permission granted |
| --- | --- | --- |
| `portfolio_holdings` | All actual broker positions | Analyze existing holdings, regardless of purchase allowlist |
| `research_universe` | Explicit permitted research/monitoring set | Research unheld securities; no purchase permission |
| `new_purchase_allowlist` | Explicit permitted new-purchase set | Create a research BUY TradeProposal; never execute it |

Research and new-purchase defaults independently retain AAPL/MSFT/SPY. A null research
universe permits holdings research only; an empty purchase allowlist permits no purchases.
VOO is the benchmark, not an implicit purchase authorization. Existing holdings, including
other symbols and fractional holdings, are not classified as forbidden purchases or marked
for liquidation. All holdings remain in portfolio analytics. New agent orders retain the
whole-share, long-only, buy-only, no-margin/options/shorting/leverage/complex-order constraints.
Unknown instruments or margin evidence may block a hypothetical risk pass, never cause a sale.

`InvestmentPolicy.may_research` implements research permission. `/research/{symbol}` uses
its configured universe. To research a holding outside that set, supply the dedicated
broker-read bearer token; the server checks authenticated broker holdings before obtaining
research data. Research evidence supplied by a caller cannot grant itself permission.
`risk.proposals.create_trade_proposal` rejects new BUY proposals outside the purchase
allowlist even when the security is held or researchable. Proposals remain local evidence
with `execution_available: false`; they are separate from the older synthetic Phase 4 API.

## Experimental capital is not portfolio value

`agent_experimental_capital_limit` defaults to USD 160. `max_total_exposure` and
`max_experimental_capital` have been removed; old configurations fail validation rather
than silently retaining their previous meaning. There is **no default portfolio-value cap**.

`PortfolioState.experimental_attribution` identifies the experimental portion explicitly:

- Reviewed baseline ID, source, exact snapshot cutoff, completeness and eligible account IDs.
- Account/symbol quantities and acquisition cost assigned to the experiment, allowing a
  partial holding in the same symbol as a pre-existing holding.
- Exact account/order IDs belonging to the experiment. Unattributed orders are not guessed
  to be experimental simply because their symbols are on the purchase allowlist.

Attribution must match complete broker inventory: no duplicate/unknown account, position or
order references, excess quantities/cost basis, missing order prices/fees or stale cutoff.
A full-position allocation must use the known full cost basis. Partial-lot cost is an
explicit reviewed input, not a pro-rata guess. Authenticated attribution is an owner/importer
assertion; broker data alone cannot distinguish pre-existing from agent-owned shares.
A reviewed empty allocation explicitly means no experimental holdings/orders. Missing
attribution remains unknown and blocks hypothetical approval. It never defaults to zero.

Utilized capital = assigned remaining acquisition cost + assigned remaining open BUY
notional and fees. Proposed capital adds the hypothetical BUY notional and explicit fees.
Utilization and remaining capacity use only the experimental USD 160 cap; unrealized gains
or losses do not change the acquisition-cost allocation. This measures deployed capital,
not lifetime turnover. Updating attribution after fills requires reviewed ledger evidence;
no automatic rebasing or background attribution is implemented.

All outstanding BUY commitments in the target account still reserve settled cash, including
non-experimental orders. Cash in another account or unsettled funds cannot finance a
proposal. Broker buying power is an additional available-funds ceiling, never a substitute
for settled cash. Portfolio-wide marked exposure remains a reported metric and a no-leverage
check, not a USD 160 ceiling. Optional owner-configured hard position/concentration caps
remain null; they are separate from informational warnings.

## Owner decisions and safety controls

The [initial configuration](investment-policy.initial.json) and
[JSON Schema](investment-policy.schema.json) record long-term capital growth, VOO / S&P 500
benchmark, VOO comparison, daily research review, weekly portfolio review and rule/event-driven
rebalancing without automatic execution. These are policy declarations, not scheduled jobs
or calculated benchmark performance. No entry/exit signals are implemented.

Kill switch, audit and future human approval remain mandatory. Proposals require nonblank
ownership, entry and exit/invalidation theses; presence does not certify investment quality.
Maximum experimental loss, maximum daily loss, freshness tolerance and daily-loss timezone
remain null and fail closed. Experiment baseline/attribution and any target allocations
must be explicitly supplied. No loss limits, target allocations or thesis content are invented.

The deterministic evaluator recomputes reconciliation, checks required controls and current
kill-switch state, account cash semantics, marks, permitted new order behavior, experimental
capital, settled cash, buying power, leverage and loss evidence. Loss at or above a configured
stop rejects. Daily P&L must be flow-adjusted realized plus unrealized P&L for the configured
calendar day at the snapshot cutoff. Experimental P&L must refer to the reviewed experiment
baseline. Production **read data** may inform research; no result can authorize execution.

## Authenticated broker reads and reconciliation

The existing opt-in `/broker` router and dedicated bearer token protect all new endpoints.
It remains disabled by default. The SDK continues using the external credential file and
production endpoint already configured for reads. No production calls were made during
implementation; tests inject synthetic SDK responses. Do not put credentials or account
payloads in chat, logs or source control.

| Endpoint | Behavior |
| --- | --- |
| `GET /broker/accounts/{id}/positions` | Quantities, currency, prices, equity cost basis and market values |
| `GET /broker/accounts/{id}/cash` | Total cash, settled/unsettled cash and buying power independently |
| `GET /broker/accounts/{id}/open-orders` | All pages of normalized open orders; never modifies them |
| `GET /broker/accounts/{id}/transactions?start=...&end=...` | All pages of cash activities for an explicit aware time interval |
| `GET /broker/portfolio?history_start=...&opening_id=...` | Reads all accounts, persists observation/metrics and optional reconciliation |
| `GET /broker/portfolio/{id}` | Retrieves stored evidence without refreshing the broker |
| `POST /broker/portfolio/{id}/analysis` | Local-only enrichment with reviewed experimental attribution/reference data; creates new evidence |
| `PUT /broker/portfolio/{id}/thesis` | Local-only revisioned position thesis, requiring `expected_revision` |
| `GET /broker/accounts/{id}/theses/{symbol}` | Latest local thesis and retained review history |

The first portfolio observation has no reconciliation baseline (`reconciliation: null`).
For the next observation, use the preceding observation ID and its `state.as_of` as
`history_start`. The first observation is evidence, not a claim that the account reconciled.
All state collections are required, with explicit completeness flags. Failed history/order
reads create explicit gaps, never an apparently successful empty ledger. Duplicate/malformed
pages, repeated cursors and page-limit overflow fail closed. Cash-activity windows are split
at UTC year boundaries because Webull disallows cross-year requests. Account/position/balance
failure rejects the observation. There is no automatic retry or order action.

Equity valuation uses broker quantity times `last_price`; total equity cost basis uses
absolute quantity times broker per-share `cost_price`. Unsupported contract multipliers are
not guessed. The adapter preserves broker unrealized P&L and account market-value/equity
observations when provided. Reconciliation compares those observations with normalized totals
using a one-cent valuation tolerance; ledger cash/quantity replay remains exact Decimal math.
Non-USD or mixed-currency totals are not converted using invented FX. Multi-currency accounts
are rejected by the complete snapshot adapter; existing balance reads still show each currency.

**Limits of Webull evidence:** separate endpoints do not establish an atomic cutoff, and
position last-price timestamps are not supplied. Retrieval times remain `observed_at`, not
fabricated market timestamps. Open-order remaining fees and leverage metadata are unknown.
The cash-activities API reports net cash movements but omits share quantities and settlement
component deltas. Pure cash activities have zero quantity change; trade/other activities
retain `quantity_delta: null`. In-kind transfers/corporate actions and settlement movements
cannot be reconstructed as a complete share ledger from those records. Consequently the
adapter declares non-atomic reads and incomplete transaction coverage; strict reconciliation
cannot pass solely on those responses. Complete typed/imported ledgers can be reconciled by
the engine, but the Webull observations remain diagnostic evidence until corroborated.

Reconciliation checks source/environment/window/account scope, duplicate IDs, unknown
references, currencies, cash components, cash and quantity replay, order identity/fill
progression and broker valuation agreement. Pending cancels still reserve funds. No
reconciliation discrepancy produces a sale, cancellation or rebalance.

Field mappings and read methods are based on the current official
[positions](https://developer.webull.com/apis/docs/reference/account-position/),
[balances](https://developer.webull.com/apis/docs/reference/account-balance/),
[open orders](https://developer.webull.com/apis/docs/reference/order-open/) and
[cash activities](https://developer.webull.com/apis/docs/reference/trade-cash-activity-by-type/)
references, including their machine-readable `.md` OpenAPI definitions, and the installed SDK.

## Portfolio intelligence

Metrics include total position market value; total portfolio market value (positions plus
cash); total remaining cost basis; unrealized P/L; allocation per security; concentration;
cash allocation; top ten symbol concentrations; equity/ETF/other/unknown exposure; direct
sector/industry exposure; and experimental-capital utilization. Values cover every supplied
broker holding and aggregate the same security across accounts. Incomplete scope, missing
values or unsupported currencies yield null affected totals rather than a partial total
presented as complete. Short-position aggregate cost/P&L accounting remains unknown.

Concentration is gross marked value of a security divided by portfolio equity including
cash. Strictly greater than 20% warns; strictly greater than 30% is severe. Exactly 20%
does not warn; exactly 30% is an ordinary warning. These are informational flags only.
Nonpositive/unknown equity makes weights unavailable. Legacy gross-exposure concentration
in reconciliation remains separately defined as largest security / gross exposure.

`SecurityReference` requires a source, as-of time, valid-until time and explicit verification
flag. Only unambiguous, verified data valid at the snapshot cutoff classifies individual
equities versus ETFs and direct equity sector/industry exposure. Missing, stale, duplicate
or unverified references remain unknown. An ETF issuer's industry is not fund look-through;
ETF sector/industry exposure remains unknown until reliable constituent data is implemented.

## Position theses and persistence

`PositionThesis` stores reason for ownership, original/current thesis, expected catalysts,
risks, invalidation conditions, target allocation, last review date and agent review history.
Unspecified decisions are null. Each agent review includes a unique ID, agent identity,
review time, assessment and evidence references. Reviews are chronological and append-only;
original thesis cannot be overwritten once supplied. Concurrent/stale revisions return 409.
Prior thesis versions remain in storage; missing theses never cause holdings to disappear.

Application persistence uses new additive `portfolio_observations_v3` and `position_theses_v1`
tables in the configured SQLAlchemy database (local SQLite / intended PostgreSQL). Broker
observations, metrics, references, attribution and reconciliation are retained privately.
Thesis and analysis writes affect only the local application database. No broker credentials
are stored in evidence. The offline evaluation repository separately uses
`portfolio_evidence_v3`; older v1/v2 tables remain untouched and require their matching reader.
Policy/state versions prevent silently reinterpreting old capital semantics.

The normal evaluator emits redacted structured JSON checks and digests; full explanations
and inputs are persisted by `PortfolioRepository.evaluate_and_record`. Database contents
are private, not tamper-proof against administrators. Schema bootstrap is additive; reviewed
production migrations, PostgreSQL concurrency validation, backups and retention remain open.

## Tests and remaining work

Run `.\.venv\Scripts\python.exe -m pytest -q` and Ruff. New tests cover a large existing
portfolio outside purchase permissions, independent research scope, proposal rejection,
experimental attribution/partial holdings, budget reservations, portfolio metrics, exact
warning boundaries, reference-data gaps, SDK read methods, pagination/cash history, missing
ledger data, authenticated API persistence and thesis history/concurrency. Fixtures are
synthetic; no real broker access or order lifecycle was exercised.

Remaining decisions/work: explicit experimental baseline and allocations; loss controls;
freshness/day boundaries; position thesis content and targets; verified reference provider;
full share/settlement/corporate-action evidence and coherent broker observations; FX and
non-equity valuation; operational migrations/backups. Do not enable sandbox/live execution,
automatic liquidation/rebalancing or strategy-specific entry/exit signals in this phase.
