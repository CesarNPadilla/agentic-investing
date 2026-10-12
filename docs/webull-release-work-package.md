# Phase 3 work package: Webull source and runtime release qualification

Prepared October 12, 2026 after independently accepted disposable passkey/guardian testing. The owner requested continuation and a visual launch plan. This package sequences remaining engineering; it creates no funding, environment, reset, paper or live activation.

| Work item | Dependency | Concrete acceptance artifact | Current state |
| --- | --- | --- | --- |
| R01 Source contract matrix | Webull technical response | Supported retail sandbox contract and entitlement mapped to each required timestamp/status/accounting/replay property; explicit failed/unproven cells stay closed | Questions prepared, unsent; unknown answers |
| R02 Protected key/history and reset boundary | Selected bounded guardian design; approved reset policy | Protected current-key selector/revocation and history; changed/restored/missing/partial evidence blocks; verified next NY trading day, fresh reconciliation and explicit authenticated approval before atomic reset | Disposable signature/retention verified; operational admission pending |
| R03 Webull plumbing freeze and runner | R01; private selected-account binding | Separate broker-bound frozen plumbing config and deployable sandbox-only runner; fixed SCHB scope, INTC disabled, no strategy research inference | Existing Alpaca config is not Webull-integrated |
| R04 Order/risk/ledger integration | R01, R02, R03 | Rejection, partial fill, fees/settlement, reservations, idempotence and reconnect reconciliation evidence; every-order/fill and bounded timer checks; no stale/unknown source admission | Broker-connected qualification pending |
| R05 Deployed safety qualification | Protected runtime and runner | Broker credential/token/handle/search-path isolation; current clock bound; timer, parent crash, outage, sticky stop/kill switch, expiry, rollback and remote-host evidence | Scoped fixtures verified; deployed end-to-end qualification pending |
| R06 Paper release review | R01–R05 | Actual fresh cash-account/equity baseline, owner-reviewed evidence and required scoped activation; durable month startup/session/end report | Not ready; no trial clock |

R01 and R02 can proceed in parallel. Engineering can prepare deterministic ledger/runner interfaces for R03/R04 while source contracts remain unresolved, but must not infer those guarantees or enable broker mutations. R05/R06 follow integrated evidence. A disabled task or a chat turn is not a persistent month runtime.

Scope constraints: Webull retail cash sandbox; SCHB ETF controls plumbing; actual equity denominators; separate approved USD 1,000 sleeve ceiling; current numerical semantics and reset order preserved; execution flags disabled. Strategies, historical/OOS data and production policy activation are outside this planning change.

After the one-month operational report, production work still requires strategy qualification and 60 qualifying forward sessions, live-ready source/broker controls, verified funding/environment, and explicit human live release. The [visual launch plan](visuals/trading-launch-plan.html) separates those dependencies and exposes conditional dates rather than promoting readiness.
