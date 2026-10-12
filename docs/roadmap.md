# Roadmap and phase gates

**Current roadmap snapshot — October 12, 2026:** Phase 3, pre-paper release qualification. The disposable passkey/guardian ceremony is independently complete; sandbox orders and the month trial are unstarted. See the [visual launch plan](visuals/trading-launch-plan.html), [conditional dates and remaining gates](trading-launch-plan.md), and [next release work package](webull-release-work-package.md). Earlier dated/current-phase entries below are historical snapshots and do not override current launch gates. No live release or automation is authorized.

## Risk-policy approval resolution v1.0.1 (2026-10-01)

The [owner decision package](human-review-0101.md) preserves the v1.0 proposal and creates 35 pending choices, including ten numerical limits, independent capital/funding/environment decisions, whole-account risk, operations, and v1.1 implementation authorization. No choice is approved, no v1.1 work has started, and no policy or execution path changed. Current cap $160; production daily-loss stop unset; historical qualification blocked; 2026 OOS sealed; paper 0/60 and execution disabled. Stop for human decisions.

## Risk policy specification v1.0 (2026-10-01)

The [approval-ready design](human-review-010.md) proposes a $1,000 attributed sleeve and explicit capital, loss, freshness, and approval controls. Every new value is unapproved and inactive; the current $160 cap and unset production daily-loss stop are unchanged. The [future v1.1 backlog](risk-control-implementation-backlog-v11.md) is not started. Historical qualification stays blocked, both strategies NOT_ELIGIBLE, 2026 OOS sealed, forward paper 0/60, and paper/production execution disabled. Stop for human approval.

## Controlled exploratory experiments v0.8 (2026-10-01)

Completed approved H01 re-entry-reset candidate, H03 diagnostic instrumentation, H04's three fixed cost scenarios, and separate simulated $1,000 whole-share feasibility. [Human review 008](human-review-008.md) reports adverse as well as favorable outcomes; no winner or v1.1.0 is selected. **H02 remains `DEFERRED_NOT_IMPLEMENTED_NOT_RUN`.** All results are `EXPLORATORY_RETROSPECTIVE`; the $1,000 case is `CAPITAL_FEASIBILITY_EXPLORATORY` and does not change the current $160 policy cap. The 2025 comparison is research-informed; 2026 OOS remains sealed. Both strategies NOT_ELIGIBLE, forward paper 0/60, paper/production DISABLED. Stop for human review before v0.9.

## Strategy design and controlled preregistration v0.7 (2026-10-01)

H01 re-entry reset, H02 holding-limit exit review, H03 exposure decomposition, and H04 fixed cost sensitivity are [preregistered](strategy-experiment-preregistration-v07.md) for human review. H01/H02 are separate draft candidate IDs, not strategy versions. The 2025 exploratory period is research-informed, not a fresh holdout. The [$1,000 feasibility plan](examples/exploratory-retrospective-v07/capital-feasibility-plan.json) remains NOT_RUN and proposed only; $100,000 normalized capital, the current $160 policy cap, and historical $160 results remain distinct. No candidate backtest, v1.1.0 implementation, OOS access, paper clock, or execution change occurred. See [human review 007](human-review-007.md); stop before v0.8 until human approval.

## Proposed experimental capital planning update (2026-10-01)

The human proposes **$1,000** as a future initial experimental-capital limit. This is a planning proposal, **not** an approved Investment Policy change, deposit confirmation, or trading authorization. The current $160 policy limit and Risk Engine controls continue to govern any actual investment activity until separately approved and changed. The existing investment portfolio stays separate. Normalized strategy-research capital remains **$100,000**; completed $160 exploratory evidence is retained unchanged.

For the next exploratory phase, [preregistered $1,000 feasibility plan](examples/exploratory-retrospective-v07/capital-feasibility-plan.json) fixes the unchanged swing v1.0.0 definition, 2023â€“24 development/2025 validation periods, current-vintage data and VOO proxy, whole-share execution assumptions, and measures for affordability, skipped/rejected orders, concentration, cash utilization, turnover, costs, and drawdown. **Status: NOT_RUN.** It cannot grant paper or production eligibility or justify tuning parameters for $1,000. The 2026 OOS stays sealed; paper and production execution remain disabled; forward paper remains 0/60.

## Exploratory retrospective sandbox v0.6 (2026-10-01)

Implemented a separate, nonpromotable `EXPLORATORY_RETROSPECTIVE` runner over 2023â€“24 development and 2025 validation only. The unchanged swing v1.0.0 produced counterfactual trade diagnostics; long-term v1.0.0 remains unready. Qualifying validation remains blocked. The 2026 OOS is sealed, both strategies NOT_ELIGIBLE, forward paper 0/60, and paper/production execution disabled. See [review 006](historical-evidence-review-006.md). Stop for human review before any v1.1.0 design, optimization, OOS release, or paper work.

## Historical evidence qualification v0.5 (2026-10-01)

Implemented a versioned, provider-neutral corporate-action ledger and bounded
raw-price adjustment diagnostics. Alpaca returned 93 supported split/dividend
events through 2025, but only one sampled split has fully corroborated terms;
historical publication and complete event coverage remain unproven. VOO total
return is not qualified. Both strategies remain NOT_ELIGIBLE and 2026 OOS is
sealed. See [review 005](historical-evidence-review-005.md). That review preceded the separately requested v0.6 exploratory phase; it did not authorize qualifying validation or paper execution.

## Strategy Experiment Lab v0.1 (2026-09-30)

Implemented LONG_TERM_QUALITY_GROWTH v1.0.0 and SWING_TREND_MOMENTUM v1.0.0,
visible eligibility/exit-review diagnostics, immutable preregistration, durable OOS
exposure protection and three predetermined development-only probes. All 15 synthetic
runs replay identically; both hypotheses are NOT_ELIGIBLE. See the
[human review](strategy-experiment-review.md), [runbook](experiment-lab-runbook.md)
and [completion report](experiment-lab-completion.md).

Next proposed task: a validated PIT historical market/fundamental/thesis import with
calendar/action/revision provenance, plus explicit owner review of UNSET controls and
simulation-policy restrictions. No real historical investment validation, optimization,
forward-paper session, broker order or production enablement is claimed. Stop for review.

## Backtesting & Strategy Validation Engine v0.1 (2026-09-30)

Implemented an offline shared-strategy harness with point-in-time views, raw-price
next-session fills, independent risk review/rechecks, corporate-action ledger, metrics,
immutable experiments, explicit holdout folds and paper-eligibility reports. See
[completion report](backtesting-completion.md) and [runbook](backtesting-runbook.md).
Current whole-share/buy-only/USD 160 sleeve and swing forward-evidence policy remain
enforced, limiting experiments accordingly. No paper/live broker orders or optimization.
Next proposed work: provenance-validated historical data and action/calendar vintages,
plus owner review of the documented policy constraints. Stop for human review first.

## Opportunity & Strategy Engine v0.1 completed (2026-09-30)

Persistent opportunities now bridge structured research/theses to separate versioned
long-term and experimental swing strategies, deterministic indicators, bounded proposals
and independent risk/human review. Production execution remains disabled. See
[completion report](opportunity-strategy-completion.md) and [runbook](opportunity-strategy-runbook.md).
The offline backtesting task is now implemented above. Historical provider and
policy/qualification gaps remain; no strategy has qualified for forward paper trading.

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

Long-Term Research Agent v0.1 (ADR-016) adds persistent evidence-linked assessments,
reviewed KPI assumption evaluation, separate thesis direction/lifecycle, multi-method
reported valuation, observation-linked portfolio context, and targeted daily/quarterly
research with durable run audits and event receipts. It exposes internal latest/history
and unranked Mag7 comparison interfaces. No broker or strategy capability is added.
Next research task: a provenance-validated SEC/IR fundamental adapter with amendment,
period/unit and company-KPI tests, followed by reviewed company research plans. Live news,
reference coverage, authenticated API exposure and operational worker/migration work remain.
See [research runbook](long-term-research-runbook.md).

Incremental foundation review (ADR-015): startup JSON policy configuration, evidence-preserving
analysis updates and authenticated thesis revision history are implemented. See the
[current gap analysis](phase2-policy-gap-analysis.md). Next: a provenance-preserving complete
ledger import/reconciliation workflow, with synthetic settlement/corporate-action tests and
no order actions. Database migrations/restore validation remain an operational gate.

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

Historical qualification review 002: raw Alpaca development/validation bars and
provider-neutral adapters are in place, but FMP statement entitlement returned
HTTP 402 and corporate-action creation vintages remain unproven. No qualifying
validation or 2026 OOS run was performed. The next research milestone requires
entitled, revision-auditable filing data and action vintages, then a frozen
development/validation run. The paper clock stays 0/60 and execution disabled.
See [historical review 002](historical-research-review-002.md).

Historical qualification v0.3 adds tested SEC accession-level reconstruction.
The next evidence requirement is original archive-level XBRL verification and
a defensible public-availability convention, followed by corporate-action
vintage qualification. No strategy validation or OOS phase opens yet. See
[review 003](historical-research-review-003.md).

Version strategies and datasets. Measure return, benchmark, drawdown, win/loss, volatility,
risk-adjusted performance, and agent decisions. Control look-ahead and survivorship bias.
Gate: predefined acceptance criteria and demonstrated paper behavior. No live execution.

## Phase 4 - Human-approved trading

Phase v0.9 adds isolated synthetic risk diagnostics and a control inventory; see
[human review 009](human-review-009.md). The authorized experimental cap is still $160;
$1,000 remains an unapproved planning scenario. Daily-loss and other hard maxima
remain undefined. Qualifying validation is blocked, 2026 OOS sealed, forward paper
0/60, and paper/production execution disabled.

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

## Risk policy reconciliation v1.0.2

[Owner review 0102](human-review-0102.md) records N01â€“N10 numerical design approvals with original semantics and auditable user-message provenance. All 25 remaining decisions, including separate CAP-A, funding, environment use and AUTH-V11, remain pending. Next: explicit owner choices for whole-account loss, portfolio exposure, trusted sources, operational ownership and exceptions. Current executable cap remains $160; controls inactive; v1.1 not authorized or started; historical qualification blocked, 2026 OOS sealed, forward paper 0/60 and paper/production execution disabled.

## Risk policy approval reconciliation v1.0.3

[Owner review 0103](human-review-0103.md) records all 35 responses as APPROVE_AS_PROPOSED. CAP-A design and AUTH-V11 conditional implementation proposal are approved; concrete account loss/exposure limits, named sources/roles, funding evidence and environment selection still need completion. v1.1 remains unstarted; activation and paper/live permissions remain absent; executable cap stays $160.

## Owner-requested capital cap change

[Policy revision 0.3](capital-cap-change-v03.md) configures $1,000 for local research startup, retaining revision 0.2 historical defaults. Production funding is planned, not confirmed. Production deployment/execution and remaining v1.1 risk implementation remain blocked by missing inputs and qualification.

## v1.1a independent implementation foundation

[Review 011a](human-review-011a.md): approved sleeve mathematics and synthetic boundary/replay tests implemented in isolation. v1.1 has started; full acceptance remains incomplete. Persistence, atomic reservations and runtime integration remain future work; account-wide controls and trusted operations require missing concrete inputs. Configured research cap $1,000; funding unconfirmed; execution disabled; 2026 OOS sealed and paper 0/60.

## v1.1b synthetic persistence foundation

[Review 011b](human-review-011b.md): durable diagnostic journal, atomic appends and sticky loss/manual latch implemented with isolated SQLite fixtures. 168 targeted tests pass. Next: atomic reservations and PostgreSQL qualification; actual baseline/reset, whole-account rules, trusted sources and runtime integration remain outstanding. Research cap $1,000; funding unconfirmed; execution disabled; 2026 OOS sealed; forward paper 0/60.

## v1.1c synthetic reservation foundation

[Review 011c](human-review-011c.md): atomic fixed-budget cash/sleeve reservations, digest-bound idempotency and partial/terminal lifecycle implemented in isolated SQLite. 190 targeted tests pass. Next: PostgreSQL serializable qualification and atomic risk/latch/reservation integration. Concrete whole-account rules, trusted data/owners and verified funding remain missing; research cap $1,000, execution disabled, OOS sealed and paper 0/60.

## v1.1d PostgreSQL atomic foundation

[Review 011d](human-review-011d.md): combined synthetic risk/latch/reservations qualified on disposable PostgreSQL 17.11. 204 targeted tests passed without skips. Runtime/API integration, authoritative marked/account evidence, baseline/reset ownership, whole-account rules and production security/migrations/recovery remain outstanding. Research cap $1,000; funding unconfirmed; execution disabled; OOS sealed; paper 0/60.

## v1.1e synthetic evidence foundation

[Review 011e](human-review-011e.md): quote/snapshot/session fixture qualification and digest-bound review expiry implemented, with atomic evidence-aware reservation checks. 241 targeted tests passed on isolated PostgreSQL without skips. Real providers/clock/roles, baseline/reset, account-wide policy and production integration remain pending. Research cap $1,000; funding unconfirmed; execution disabled; OOS sealed; paper 0/60.

## v1.1f synthetic loss-accounting foundation

[Review 011f](human-review-011f.md): frozen initial/daily baselines, signed-flow-adjusted sleeve P&L and atomic accounting/latch persistence implemented. 263 targeted tests passed on isolated PostgreSQL. Calendar-driven boundary selection, trusted ledger/equity, authenticated baseline correction/reset and whole-account policy remain pending. Research cap $1,000; funding unconfirmed; execution disabled; OOS sealed; paper 0/60.

## v1.1g crash/outage recovery qualification

[Review 011g](human-review-011g.md) consolidates readiness and qualifies actual disposable PostgreSQL process restart, committed/uncommitted state recovery, lost-ack retry and outage rejection. 271 targeted tests passed without skips. Trusted inputs, whole-account policy, roles/reset, backup/restore and runtime/production deployment remain pending. Research cap $1,000; funding unconfirmed; execution disabled; OOS sealed; paper 0/60.

## v1.1h current-readiness audit

[Review 011h](human-review-011h.md) and the machine-readable report preserve all 17 outstanding gates. 135 targeted tests passed this phase; no PostgreSQL/runtime changes. Next dependent controls require explicit whole-account loss/exposure choices, named trusted sources/roles and verified funding/environment. Full v1.1 remains incomplete; research cap $1,000, execution disabled, OOS sealed and paper 0/60.

## Concrete owner-input step

[Remaining owner inputs](remaining-owner-inputs-v11.md) provides the next response form and source-bound register. Existing approvals remain recorded; no further implementation milestone is declared complete. First required choices: whole-account daily-loss amount/method and portfolio gross/security limits/denominators. Sources, owners, funding and environment evidence follow.

Owner input update: whole-account dollar daily-loss stop recorded as $1, inactive pending its measurement/day/reset method and separate activation. Portfolio gross/security limits remain unspecified. See [input register v2](examples/remaining-owner-inputs-v11/input-register-v2.json).

Owner clarification: daily whole-account stop is 1% of total account equity, superseding the historical $1 dollar input. Whole-portfolio gross limit is 100% of total account equity. Both remain inactive pending measurement/denominator timing and activation; per-security concentration is still unspecified. See [input register v3](examples/remaining-owner-inputs-v11/input-register-v3.json).

Owner concentration input: maximum per-security exposure is 10% of total account equity. Daily loss 1% and gross exposure 100% remain recorded. Measurement/denominator timing, existing-breach treatment and activation remain unresolved; see [input register v4](examples/remaining-owner-inputs-v11/input-register-v4.json).

## v1.1i owner-defined whole-account foundation

[Review 011i](human-review-011i.md): 1% start-of-day daily loss and 100%/10% current-equity gross/security diagnostics implemented in isolation. 233 targeted tests passed. New York calendar midnight and retain/report/block-new-buy/human-review existing-breach rules are recorded and tested. Reset/check-frequency, diversification rules, trusted evidence and whole-account persistence/runtime integration remain pending. Research cap $1,000; funding unconfirmed; execution disabled; OOS sealed; paper 0/60.

## v1.1j reset and monitoring contracts

[Review 011j](human-review-011j.md): owner-defined external-human reset ordering and every-fill/order plus 1-5 second active-scope deadlines implemented as synthetic contracts. 259 targeted tests passed; actual named identity, providers, durable reset and live scheduling remain pending. Research cap $1,000; funding unconfirmed; execution disabled; OOS sealed; paper 0/60.

## v1.1k owner and provider selection

[Review 011k](human-review-011k.md): declared human owner and Webull quote/account APIs plus NYSE published calendar recorded with exact instruction provenance. Readiness consumes register v8 without promoting any gate. API entitlement, external authentication, source reconciliation and calendar integration remain pending; live release remains blocked.

## One-month Alpaca paper trial preparation

[Preparation review](alpaca-paper-month.md): explicit paper-trial authorization recorded; owner selected account/controls preparation first. Alpaca account read-only preflight passes, empty and unblocked. Frozen strategy, integrated paper controls and persistent runner remain prerequisites. No live permission or 60-session waiver.

## Alpaca paper bid/ask preparation

[Quote preparation](alpaca-paper-quote-preparation.md): isolated read-only IEX bid/ask observations, provenance and 30-second freshness diagnostics implemented. Authenticated connectivity check passes; stale/status-unverified sample remains blocked. 39 tests pass. Calendar/status/clock, durable control integration and strategy selection remain prerequisites; trial not started.

Paper quote preparation: [isolated Alpaca IEX bid/ask acquisition](alpaca-paper-quote-controls.md) now validates response provenance/timestamps/prices; 33 targeted tests pass. No status inference or release promotion.

Paper session preparation: [bounded NYSE calendar controls](alpaca-paper-calendar-controls.md) implemented; 15 new calendar tests, 67 targeted tests pass. No broker-status inference, reset mutation or runtime activation.

Combined paper preparation: [account observation, durable preparation state and frozen plumbing intents](alpaca-paper-control-pipeline.md) tested together; 83 targeted tests pass. Dedicated $1,000 account selected but not yet bound. Full reconciliation/order runtime remains incomplete.

Paper fill preparation: [bounded activities and whole-share fill replay](alpaca-paper-fill-controls.md) implemented; 94 targeted tests pass. Dedicated account retains $1,000 baseline; no fills/settlement or execution runtime qualification inferred from empty activity data.

Durable paper accounting: [immutable activity IDs and atomic fill replay](alpaca-paper-durable-fills.md) implemented; 100 targeted tests pass. Verified dedicated account initialized private ledger; no real fills or execution release.

Paper cash preparation: [fee/flow classification and account comparison](alpaca-paper-cash-controls.md) implemented; 108 targeted tests pass. Real empty-account cash matches ledger; cutoff/publication/settlement blockers remain.

Combined reconciliation/settlement/clock: [review](alpaca-paper-settlement-clock.md) records complete quantity comparison, owner-approved paper settlement model and fail-closed Windows Time diagnostics. 118 targeted tests pass; clock source/error policy and full order runtime remain pending.

Paper status step: [tape-specific halt/resume and continuity diagnostics](alpaca-paper-status-controls.md) implemented; 128 targeted tests pass. Real stream entitlement/bootstrap and pending clock policy remain unqualified.

Paper protocol/lifecycle: [durable submit and uncertain-response review](alpaca-paper-order-lifecycle.md) records 137 passing targeted tests; order step 50%, checklist 56% (20/36). Actual mutations remain blocked; release/runner integration incomplete.

Integrated paper observer/reservations: [review](alpaca-paper-integrated-observer.md) records two real read-only cycles, 143 passing targeted tests and 58% checklist completion (21/36). Order lifecycle 75%; continuous runner remains 25% because hard timers/events/recovery remain incomplete. Clock decision pending.

ETF-only trial continuation: [SCHB ownership/restart qualification and routing](alpaca-paper-etf-integration.md) implemented. Next gates are authenticated owner service recovery, initial status/continuity, complete flow reconciliation and persistent supervised runtime. INTC remains disabled; no trial launch or live permission.

October 7 paper preparation: [explicit current checklist](alpaca-paper-readiness-current.md) records 23/36 accepted components (64%), launch 0%, and actual disposable service-crash restart rejection. Read-only Windows task is installed disabled; source/authority/runtime launch gates remain pending. Historical recovery requests are superseded by scoped read-only acknowledgement only, not risk-reset qualification.

Diagnostic backup follow-up: [private snapshot integrity](alpaca-paper-diagnostic-backup.md) is qualified with source read-only access and overwrite refusal; 318 selected tests pass. Protected restore/reset and provider evidence remain dependencies. No additional checklist criterion is promoted.

Webull alternative evaluation: [retail sandbox feasibility](webull-sandbox-feasibility.md) verifies read-only account, cash/activity and SCHB data access with owner-supplied sandbox credentials. Account selection and dedicated USD 1,000 baseline remain pending; neither provider migration nor execution is activated. Alpaca support request is deferred; historical Alpaca readiness is not carried into Webull qualification.

Webull baseline amendment: [actual whole-account sandbox equity is approved](webull-sandbox-equity-amendment.md), replacing the dedicated USD 1,000 requirement for this evaluation. The experimental sleeve ceiling remains separate. Next: select cash/margin account, establish fresh bound baseline, and qualify source/authority/runtime gates.

Webull controller preparation: cash selection and actual-equity design are recorded; scoped runtime file/DACL denials are verified. The [untrusted request contract](webull-control-request-boundary.md) is implemented without admission or reset authority. Next: protected OS-authenticated transport, durable replay/state admission and Webull-specific owner approval, alongside unresolved provider status/accounting/event contracts. Trial launch remains 0%; live execution is not authorized.

Webull review continuation: [action-bound signature verification and durable review evidence](webull-owner-review-evidence.md) pass 28 synthetic-key tests, including restart and concurrent replay rejection. Real owner signing, immutable controller deployment, independent recovery anchoring and atomic reset approval remain next authority dependencies. Webull must supply the prepared status/accounting/event evidence; unknown source guarantees cannot be replaced by a valid review signature. Launch remains 0%.

Separate Webull owner-review app: seven endpoint tests pass, with the combined review batch at 35/35. Prepared development UI has no actual owner envelope or deployed authority. Complete protected controller/state/recovery staging and source-qualified review preparation before requesting the direct owner ceremony.

Protected Webull review source: [six-file pinned package and owner-run installer](webull-review-protected-source-install.md) are prepared; the source installation batch is 75%, awaiting actual elevated owner installation and independent inspection. Frozen consumption checkpoint diagnostics pass seven tests without recovery authority. Protected interpreter/dependencies, process lifecycle, private state and independently protected recovery remain later dependencies; trial launch remains 0%.

Owner source-installation follow-up: independent read-only hashes/ACLs verify the installed pinned review release; the source batch is now 100%, runtime disabled. Initial isolated interpreter/library inventory remains tied to owner-profile Python and development packages. Next engineering work is a protected execution environment and its complete search-path/lifecycle qualification; current source protection does not release the app or trial.

Embedded review environment continuation: [pinned CPython and 17 vendored review libraries](webull-review-environment-install.md) pass fixed-search-path and synthetic signature/journal smoke checks. Environment installation is 75%, pending direct elevated owner installation and independent inspection. Native-library/token/lifecycle, state/recovery, source contracts and actual owner ceremony remain separate gates; launch stays 0%.

Elevated environment installation: owner-authorized engineering applied the pinned package and independently inspected 678 payload hashes/780 exact ACLs; environment installation is 100%. Installed isolated imports/native cryptography and current-process native path enumeration pass within their scope. Protected state/recovery and full identity/lifecycle/source qualification remain pending. No app or trial activation follows from installation.

Recovery reference continuation: eleven write-ahead intent tests cover actual abrupt exits and replay/rollback against a retained reference. Staged code remains outside the installed release. Next dependency is the owner's explicit independent reference-writer choice; guardian identity or offline reference design must precede provisioning and real review state. Source contracts and launch gates remain pending.

Guardian choice received: dedicated non-admin identity selected. Prepared disabled-account/empty-tree provisioning and disposable ACL configuration checks are complete; 2/3 (67%), pending the owner's direct local password entry and independent inspection. Transport, standard-token owner isolation, guardian lifecycle, reference integrity and actual review/reset integration remain future qualification work.

Guardian provisioning completed: live account/group and six directory ACL/inventory checks pass; 3/3 (100%), both accounts disabled. Next engineering work is protected guardian code/transport and lifecycle/reference integration, followed by actual token qualification. No service, real reference or trial activation is inferred from provisioning.

Webull guardian continuation: [separate reference protocol and actual-token fixture](webull-guardian-reference-protocol.md) pass 20 synthetic tests; 558 selected regression tests pass. Guardian alone retains signed intent/confirmation, reading rather than writing the owner consumption journal. Strict native identity dispatch is mock-tested; actual transport/service/lifecycle are pending. The dummy-file guardian-token fixture is 2/3 (67%), awaiting direct owner-held password entry and independent receipt inspection. Both accounts remain disabled; trial launch remains 0%.

Webull guardian boundary follow-up: the owner-completed actual-token dummy-file receipt is independently accepted at 100%. A same-owner non-admin desktop-token probe passes 37 denied mutation/deletion handles and six read controls without changing directory descriptors. Staged guardian-specific bounded transport passes six dispatch/framing tests; protected guardian execution, actual cross-account transport/lifecycle and real review integration remain pending. Completed fixtures need no repetition; both accounts stay disabled and launch stays 0%.

Protected guardian package: [687 pinned payloads and 792 protected objects](webull-guardian-protected-release.md) are installed and independently verified; isolated imports and synthetic cryptography pass. Installation is 100%. The protected guardian-server/elevated-owner-client synthetic pipe fixture is prepared, syntax checked and native-client compiled (2/3, 67%); direct local guardian password entry and receipt inspection remain required. No service, real reference or reset is deployed; both accounts remain disabled and launch stays 0%.

Guardian cross-account verification: the owner-run elevated-client synthetic pipe fixture is independently accepted at 100%, with receipt/readiness/empty diagnostics and unchanged installed hashes/ACLs verified. The standard-owner-token client variant is prepared (67%) and passes syntax, native compilation and missing-pipe identity-restoration checks; actual guardian connection awaits local password entry. No service, real reference or reset is admitted. Both accounts remain disabled; launch stays 0%.


Standard-owner connection verification: the owner completed receipt `guardian-pipe-result-883afc11-eebd-46c3-901a-738b6a1942c1.json` and its wrapper summary. Independent inspection verifies standard client mode, effective token/restoration flags, receipt hash, current wrapper hash, matching probe IDs, readiness and empty diagnostics. All 687 installed payload hashes and 792 exact ACL objects remain verified; both accounts are disabled. This scoped batch is 3/3 (100%). The prior 67% instructions are historical; do not rerun the completed fixture. Next engineering work is runtime/other-identity rejection and deployed lifecycle/owner-app isolation, before real signature/reference/reset admission. No service, real review state or launch gate is promoted. Trial launch remains 0%, forward evidence 0/60 and overall readiness unquantified.

Guardian runtime-rejection continuation: [prepared two-account DACL-denial fixture](webull-guardian-runtime-denial.md) requires actual runtime ACCESS_DENIED and a standard-owner positive control on the same live pipe. Parser/native checks and disposable denied/allowed sequence pass; preparation is 67%, actual execution/receipt inspection awaits local account passwords. No installed package/service or real approval/reset is changed. Both accounts remain disabled; launch stays 0%.


Runtime DACL-denial verification: the owner-completed two-account fixture is independently accepted at 3/3 (100%). Actual AgenticPaperRuntime reports Win32 ACCESS_DENIED with no payload, followed by standard-owner success on the same guardian pipe. Nested receipts, five hash links, retained child source, gate/readiness, empty diagnostics and installed package ACLs/hashes are verified; both accounts are disabled. Earlier 67% password instructions are superseded. No repeat is needed. Other-identity/remote-host rejection, deployed process/service lifecycle, real signed reference/reset integration and provider evidence remain pending. No service, reset or execution is activated; trial launch remains 0%, forward evidence 0/60.

October 9 guardian failure-path continuation: four native installed-code checks pass under engineering identity (missing client, partial/oversized frame, wrong configured owner), with closed pipe, no residual impersonation and zero reference-handler calls. The actual guardian-token/self-caller wrapper is prepared at 67% and needs locally held Guardian credentials. No account, package, service or real reference/reset is activated; launch stays 0%.


Actual guardian failure-path verification: owner receipt `guardian-failure-paths-result-5c115cf7f5904616839357503a83e3ea.json` is independently accepted at 3/3 (100%). Missing client, partial/oversized frame and guardian self-caller rejection fail closed under the actual guardian token. All scenario/log pairs, empty diagnostics, retained literal/source hashes and exact protected file ACLs match; installed package hashes/ACLs remain verified and both accounts are disabled. Earlier 67% password/retry instructions are superseded. No rerun is needed. Unrelated identities, remote hosts, deployed owner app/service lifecycle, real signed reference/reset and provider contracts remain separate unresolved gates. Trial launch stays 0%, forward evidence 0/60; no service, reset or execution is activated.

October 9: installed owner-app missing-state lifecycle diagnostic complete (ten HTTP checks, forced shutdown, engineering token); next is guardian write-ahead integration and standard-owner process qualification. Trial launch remains 0%.

October 9: guarded review integration/source preparation and engineering native reply/client tests complete. Actual guardian reply fixture is prepared; owner credential entry is next. Standard-owner/service/real recovery qualification and Webull provider contracts remain open.

October 9: elevated-owner native guardian reply fixture and standard-owner missing-state app process independently complete. Standard-owner guardian exchange preparation is complete; direct local guardian credential entry is next. Real reference/passkey, service/reset lifecycle and provider evidence remain pending.

October 9: standard-owner guardian reply fixture verified; signed synthetic native integration completes three success/ambiguous-delivery scenarios and related regressions (69 tests). Continue protected reference/app/service lifecycle and actual signing/recovery qualification; provider evidence remains unresolved.

October 9: recovery inspection implementation and new protected guardian package complete (67 relevant tests; 689 hashes/794 protected objects; four installed-interpreter synthetic states). Next is protected review-host lifecycle and owner-app transport integration, then actual signed-reference/passkey qualification. No service or trading activation.

October 10: review-host lifecycle model and native owner-app integration complete for engineering scope (33 tests). Next: protected provisioning/configuration, host package and external supervision with actual guardian signed-reference/crash qualification. Trial launch remains disabled.


October 10: native suspended-start process supervision passed nine Windows tests; the related host/package batch passed 23 tests. The separate protected host/supervisor release is installed and audited (692 payload hashes, 798 protected objects), with three installed-interpreter engineering checks passed. See [guardian process supervision](webull-guardian-process-supervision.md). Implementation, package installation and guardian-fixture preparation are each 100% for their scope; actual guardian supervision verification is 0% and needs the existing guardian password entered locally in the prepared script. No service, real signed reference, reset or trial is activated; trial launch remains 0%.


Actual guardian supervision accepted: receipt 988bab68bbb84aaa92605d8afaf7dca6 and its wrapper independently verify all four termination/identity cases, zero remaining job processes, exact probe ACL/hash, wrapper/receipt hash links and clean diagnostics. The 692-file/798-object installed release remains audited, and both accounts are disabled. Actual guardian supervision is now 100% for this synthetic fixture; earlier 0% retry instructions are historical and no repeat is needed.

The next engineering batch also passed six native host interruption cases: stop and deadline at the start, retained-intent and consumed-owner-review boundaries. Expected start/intent/journal evidence survives process termination, confirmation is absent and restart cannot open transport or change retained state. This batch is 100% for engineering-token synthetic signatures and injected pipe dispatch. Actual guardian signed-host operation, protected configuration/provisioning, service lifecycle, owner passkey signing, remote-host denial and Webull technical contracts remain separate unresolved gates. No service, real review state, reset, order or trial was activated. Trial launch remains 0%, forward evidence 0/60 and overall readiness unquantified.


Host configuration engineering now validates externally pinned bytes, installed release, current envelope/public credential, distinct identities and fixed separate provisioning paths. Explicit false scope flags and bounded JSON parsing prevent coercion and ambiguous inputs. See [configuration contract](webull-guardian-host-configuration.md). Configuration material checks are 100% for their staged scope (45 related tests passed); filesystem provenance, actual guardian/owner token roles, protected loader and signed-host/service operation remain unqualified. No real provisioning, installed release change, reset or activation occurred; actual guardian supervision needs no repetition and trial launch remains 0%.


Protected configuration loader continuation: 12 native file/security rejection cases and related configuration/release regressions pass (39 tests). Version-four loader/config package installation is complete with 694 hashes and 800 protected objects verified, and an installed engineering protected read/parse passed. See [protected loader and next local command](webull-protected-config-loader.md). Engineering, installation and guardian fixture preparation are each 100% for their scope. Actual guardian protected-read verification is 0% and needs the existing guardian password entered locally; no earlier fixture needs repetition. No real journal/reference, service, reset or trial was activated; both accounts are disabled and trial launch remains 0%.


Actual guardian protected-loader verification accepted: fixture c586a8342cea4d8e880914d4430aec31 is independently verified. Configuration/probe/receipt/wrapper hashes, two exact administrator-owned protected file ACLs, configured actual role bindings, empty stderr/expected stdout and receipt time inside the synthetic envelope window match. All 694 installed hashes and 800 protected objects remain audited; both accounts are disabled. This scoped actual guardian read is now 100%; prior 0% password instructions are historical and no repeat is needed. The fixture loaded synthetic public material only. Actual journal/reference directory provisioning, signed-host/app operation, service lifecycle, owner passkey signing, Webull technical contracts and atomic reset admission remain unresolved. No service, real signature/reference/journal, reset, order or trial was activated. Trial launch remains 0%, forward evidence 0/60 and overall readiness unquantified.


Synthetic review layout provisioning completed with three exact administrator-owned protected ACLs and an empty owner journal. The actual standard-owner process can obtain a journal write handle without changing bytes and cannot create reference files. See [layout qualification and next guardian command](webull-review-layout-provisioning.md). Provisioning, standard-owner access and guardian fixture preparation are each 100% for their scope; actual guardian journal/reference access is 0% and requires the existing guardian password locally. No real approval/reference, service, reset or execution was activated; both accounts are disabled and trial launch remains 0%.


Actual guardian synthetic layout access accepted: receipt c28a02f0aaf8413c893a871cc11d73e6 independently verifies the configured guardian identity, empty-journal read, denied journal write open and retained synthetic marker write. Eight retained hash links, five exact protected-object ACLs, marker ownership/scope, actual role bindings, clean diagnostics and disabled accounts match. The configuration was current at the fixture time; the owner journal remains byte-identical and contains no consumed review, intent or confirmation. The 694-file/800-object package remains audited. Actual guardian layout access is 100% for this synthetic fixture; earlier 0% password instructions are historical and no repeat is needed. Signed owner consumption, actual signed-host/app operation, service lifecycle, independent provisioning history, real owner passkey ceremony, provider contracts and atomic reset admission remain pending. No host/service, real approval/reference, reset, broker order or trial was activated. Trial launch remains 0%, forward evidence 0/60 and overall readiness unquantified.


Signed-host integration fixture engineering and protected package preparation completed. See [synthetic signed-host command and scope](webull-signed-host-integration.md). Fifty-three related tests plus fifteen follow-up fixture/package checks pass; installed synthetic signature verification and bootstrap compilation pass. Version five is audited at 697 payload hashes/803 protected objects. Engineering, installation and fixture preparation are each 100%; actual standard-owner/guardian signed protocol run is 0% and needs the existing guardian password locally. The generated software signature is not a real owner passkey approval; no service, reset or trading is activated. Both accounts remain disabled and trial launch is 0%.


Actual signed-host fixture accepted: receipt 58ca9e1d14134b5bbfe6986619db8fb6 independently verifies one cryptographically valid synthetic owner-journal consumption, matching guardian intent/confirmation, ordered PREPARE/CONFIRM terminal evidence, actual standard-owner process and zero remaining supervised job processes. Nine retained hash links, six exact protected ACLs, four guardian-owned records and clean diagnostics match; the 697-payload/803-object package remains audited and both accounts are disabled. Actual cross-account signed-host progress is 100% for this bounded software-signature fixture. Earlier 0% instructions are historical; no rerun is needed. Real Windows Hello owner signing, deployed owner app/service lifecycle, protected provisioning history, provider guarantees, clock qualification, remote-host denial and atomic reset admission remain pending. No real approval, reset or trading is activated. Trial launch remains 0%, forward evidence 0/60 and overall readiness unquantified.


October 11: pinned owner-app engineering, protected package preparation and actual standard-owner app construction are complete (100% each). The actual construction receipt f9977c948e2b4f2f8873b01ee6d1e8c6 verifies protected context reads with an unchanged empty journal, no listener/challenge/exchange and disabled accounts. The next cross-account HTTP fixture is prepared but unrun (0%); it requires the existing guardian password entered locally. Its software-generated assertion and controlled test nonce cannot establish a real Windows Hello ceremony. See [pinned owner-app integration](webull-pinned-owner-app-integration.md). Real passkey/app/service lifecycle, provider evidence and atomic reset remain pending. Trial launch remains 0%, forward evidence 0/60 and overall readiness unquantified.


October 11 HTTP fixture correction: the reported c1a6735fb3bf4071af04aca6b8262c25 attempt failed closed with HTTP 403 while the guardian reached its five-second initial connection deadline. The retained terminal has no completed actions; the owner journal is empty and intent/confirmation are absent. Both accounts are disabled. Startup now uses a bounded ten-second pre-host readiness wait: the owner completes HTTP startup and challenge preparation, atomically publishes a context-bound marker, and only then the guardian starts the supervised host. Existing five-second pipe and fifteen-second child-job deadlines are unchanged. Eleven fixture tests and eight HTTP/host follow-up tests passed (overlapping batches); Ruff passes. The new 069895024e135b302535e931cf574caca99c62aae31724d367aded09c4a06c8c package audits 702 payload hashes/808 protected objects. Preparation is 100%; actual cross-account HTTP verification remains 0% pending the local guardian password. Earlier successful stages need no rerun. Trial launch remains 0%; no real passkey, reset or trading is activated.


Actual cross-account synthetic HTTP fixture accepted: receipt 98bfe742735e48ac832023bf06511086 independently verifies HTTP challenge/cookie/signature processing under the actual standard owner, exactly one cryptographically valid journal consumption, matching guardian intent/confirmation and ordered PREPARE/CONFIRM terminal evidence. Nine retained hash links, six exact protected ACLs, four guardian-owned records, context-bound readiness and clean diagnostics match. The supervised job reports zero processes; the HTTP close receipt and closed loopback port are verified. The 702-payload/808-object package remains audited and both accounts are disabled. Actual cross-account HTTP progress is 100% for this software-signature/controlled-nonce fixture. Earlier 0% retry instructions are historical; no rerun is needed. Real owner passkey ceremony, deployed app/service lifecycle, protected provisioning history, provider contracts, clock/remote-host qualification and atomic reset admission remain pending. No real approval, reset, broker order or trial is activated. Trial launch remains 0%, forward evidence 0/60 and overall readiness unquantified.


October 11 continuation: real-key authentication-only diagnostic engineering, protected package preparation and local ceremony preparation are each 100%. See [owner Windows Hello diagnostic](webull-owner-auth-diagnostic.md). Nineteen related tests plus two material tests pass (the earlier six-test authentication batch overlaps); Ruff, UI syntax, installed import and bootstrap compilation pass. The new protected package audits 704 payload hashes/810 objects. Only the existing public credential is pinned; owner-writable enrollment provenance remains an explicit limitation. Actual owner authentication is 0% and needs the owner to use the local page; no guardian password or guardian host is involved. No real review evidence, reset or order is issued. Both accounts remain disabled, trial launch is 0%, forward evidence 0/60 and overall readiness is unquantified.


Actual owner passkey authentication diagnostic accepted: receipt bfca45d55f164f7b9f88ef1674562c53 independently verifies the retained assertion signature, required user verification, exact localhost:8768 origin and diagnostic nonce/configuration domain binding. Configuration was current at the receipt time. Nine retained hash links, five exact protected ACLs, configured role bindings and clean diagnostics match. The owner journal is byte-identical to the provisioning receipt and contains zero reviews; the guardian reference directory is empty. Listener closure and closed port are verified; the 704-payload/810-object package remains audited and both accounts are disabled. Actual authentication diagnostic progress is 100%; earlier 0% ceremony instructions are historical and no rerun is needed. The owner-writable enrollment bootstrap remains unqualified; neither legal identity nor authenticator manufacturer is independently attested. No Webull review signature, guardian call, reset or trading is authorized. Real review/app/guardian lifecycle, trusted credential bootstrap, provider evidence and atomic reset admission remain pending. Trial launch remains 0%, forward evidence 0/60 and overall readiness is unquantified.


October 11: explicit owner credential-binding ceremony is prepared. Engineering, protected package install/audit and local ceremony preparation are each 100%; actual binding and accepted registry installation are 0% pending owner authentication. See [credential binding action](webull-owner-credential-binding.md). The binding purpose/origin/domain are distinct from the completed diagnostic, and an externally pinned candidate prevents silent credential substitution. Seventeen related tests and five follow-up binding tests pass with overlap; Ruff, UI syntax, installed import and bootstrap compilation pass. The 704-payload/810-object package is audited. Both accounts remain disabled; no listener, binding approval, registry, real review, guardian call, reset or trading is activated. Trial launch remains 0%, forward evidence 0/60 and overall readiness unquantified.


October 11 credential adoption accepted: owner receipt `de054144a60e49579df56b39a120269f` independently verifies the explicit binding signature, required user verification, localhost:8769 origin and separate binding challenge domain. Nine hashes, five ceremony object ACLs, empty unchanged journal, empty reference directory and listener closure match. Actual owner binding is 100%; no repeat authentication/binding is needed. The immutable administrator-owned accepted public credential record is installed at 100%, with exact four-ACE protection and native held-handle verification. The new registry-enforcing review factory revalidates the pinned record on each request and blocks substitution. Its separately installed package audits 705 payload hashes/811 objects; 38 relevant tests pass. An active key selector, revocation/rollback protection and actual registered app/guardian ceremony remain unqualified. The owner selected bounded guardian operation only during each owner-started review ceremony; no persistent service is authorized. The next [guardian credential-registry identity check](webull-owner-credential-registry.md) is fully prepared and needs the locally held guardian password. Both accounts are disabled; trial launch remains 0%, forward evidence 0/60 and overall readiness unquantified.


October 12 continuation: the actual guardian credential-registry fixture `9992aab98b8642d7aeade8b8ad58d8a0` is independently accepted at 100%, superseding its earlier 0% action. Protected literal source, guardian-owned receipt, clean diagnostics, signed binding/native record reads and the 705-payload/811-object package are verified; do not rerun that completed fixture. Registered owner app construction under the actual standard desktop token is also 100%, with eight retained hashes, byte-identical empty journal and empty reference directory. No listener/challenge/passkey/guardian exchange was used; account and plan values remain synthetic. Guardian-side registered-context admission engineering, new protected package and local preparation are each 100%; 40 tests pass. The actual guardian positive/changed-key check is 0% pending the locally held guardian password. See [the next bounded guardian check](webull-registered-guardian-config.md). Both accounts stay disabled; no real ceremony, service, revocation/rollback, reset, order or trial is qualified. Trial launch is 0%, forward evidence 0/60, overall readiness unquantified.


October 12 guardian registered-context receipt accepted: `f31fa556240f40128ddd7f89d48c34db` independently verifies actual guardian configuration admission and changed credential-pin denial. The protected retained probe matches its literal source and exact ACL; the receipt is guardian-owned, diagnostics are empty and both accounts are disabled. Matching owner wrapper retains eight valid hash links. The protected configuration was current at the actual probe time, matches both Windows roles and the accepted credential; original binding signature and changed-candidate rejection were independently rechecked. The 705-payload/811-object installed package remains audited. This scoped step is 100%; prior 0% execution instructions are historical and no repeat is needed. Account/plan context remains synthetic. The next integrated signing/guardian-retention ceremony needs its signed review purpose selected: a clearly labeled disposable controls-test review, or an actual reset-precondition review after account/provider evidence is ready. That choice is pending; no reset, service or trading authority follows from these fixture results. Trial launch stays 0%, forward evidence 0/60 and overall readiness unquantified.


October 12 disposable ceremony scope selected: the owner answered “A clearly labeled disposable controls-test review (recommended).” [The integrated ceremony](webull-disposable-controls-ceremony.md) is prepared with a distinct disposable-test schema, action, purpose and challenge domain; its page explicitly labels the account/plan as synthetic. It cannot promote test signatures to reset-precondition evidence. Real-review semantics remain unchanged. Engineering, separate protected package install/audit and local preparation are 100%; actual integrated signing/guardian retention is 0% pending the owner-held guardian password and direct Windows Hello gesture. Ninety ceremony/protocol tests plus 49 regression/native tests pass in distinct batches; 706 payload hashes/812 protected objects, wrapper syntax and bootstrap compilation/imports pass. The guardian waits for an assertion-verified readiness marker before starting the bounded pipe host. Preparation started no listener or ceremony; both accounts remain disabled. No service, reset, real account approval or trading is activated. Trial launch stays 0%, forward evidence 0/60 and overall readiness unquantified.


October 12 integrated disposable ceremony independently accepted: wrapper `f9ff16f53abd43f59b42988328d38b84` verifies the real owner passkey signature and required user verification, distinct disposable action/purpose/domain and approved protected credential. Exactly one cryptographically valid journal consumption matches the guardian intent/confirmation; terminal order is PREPARE then CONFIRM. Ten retained hashes, six exact protected ACLs and four guardian-owned reference records match. The supervised job exited with zero active processes; listener closure and closed port 8767 are verified, diagnostics are empty, package audit covers 706 payload hashes/812 objects, and both accounts are disabled. Actual disposable ceremony progress is 100%; earlier 0% owner instructions are historical and no repeat is needed. Account and plan remain synthetic; no actual account review, reset, service or trading is authorized. [Fresh provider-documentation follow-up](webull-provider-evidence-followup-1012.md) leaves four retail status/accounting/event guarantees open; the authenticated Webull support request remains unsent. Protected current-key/revocation/history, clock/remote-host qualification, real account review, atomic reset and paper runtime/activation remain separate gates. Trial launch is 0%, forward evidence 0/60, overall readiness unquantified.
