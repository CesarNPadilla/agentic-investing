# Phase v1.1g ? PostgreSQL crash and outage recovery qualification

**RECOVERY FOUNDATION QUALIFIED / FULL v1.1 INCOMPLETE.** Independent recovery testing now includes actual abrupt database-process termination and restart in a newly created disposable PostgreSQL 17.11 container. See [current implementation status](examples/risk-policy-v11g/implementation-status.json).

Committed reservations, initial baseline evidence, sticky loss latch and partial-fill commitments survive process restart. An uncommitted direct state change is rolled back by PostgreSQL recovery. A committed receipt deliberately discarded before the crash can be retried without duplicate capacity allocation. Unknown order status continues to hold commitments after restart, and verified synthetic terminal evidence releases only the unfilled portion. A stopped database raises a blocking typed error and creates no new reservation; existing state remains intact after recovery. No operational outage-reset/latch policy is inferred.

Persisted malformed decimal values now raise the same blocking storage error rather than leaking numeric-conversion exceptions. Recovery tests inspect only the runner-owned container: exact ID format, disposable name prefix, explicit qualification label and localhost synthetic database are required before stop/kill/start. No existing application service/database is targeted. The runner uses a fixed explicit localhost port so its connection remains valid after Docker restarts.

Validation: **8 new recovery tests; 271 targeted tests passed with no skips**. Tests exercise actual abrupt stop/start, committed versus uncommitted recovery, sticky latch/baseline persistence, partial-fill/unknown/verified terminal lifecycle, discarded-acknowledgement retry, database outage and malformed numeric state. Static checks, source digests, JSON and git diff --check pass. The initial harness run stalled because Docker changed an automatically assigned port after restart; it was terminated, cleaned up, corrected and the full suite rerun successfully. The final disposable container was removed.

Limits: this tests process/container crashes with the same disk state, not host/disk loss, backup restore, point-in-time recovery, high availability or production scale. Lost acknowledgement is simulated by discarding a committed return value, not by intercepting the network. All funds, fills, source evidence and baseline verification remain fixtures. There is no production runtime integration or human reset mechanism.

## Consolidated readiness

| Workstream | Current result | Remaining gate |
| --- | --- | --- |
| Approved sleeve mathematics | Synthetic tests pass | Qualified account/market inputs and runtime integration |
| Atomic risk/latch/reservations | PostgreSQL synthetic qualification passes | Production schemas/migrations/security and authoritative marked state |
| Evidence/review bindings | Synthetic freshness/session/digest checks pass | Real entitled providers, clock monitoring, authenticated human approval |
| Baseline/loss accounting | Frozen flow-adjusted synthetic baselines pass | Trusted reconciliation, exact calendar boundary and authenticated corrections/reset |
| Crash/outage recovery | Disposable PostgreSQL process recovery passes | Backup/restore, operations monitoring, deployment/recovery procedures |
| Whole-account risk | Unresolved | Explicit account-wide daily-loss threshold/method and portfolio exposure rules |
| Funding/operational roles | Unconfirmed/unassigned | Actual deposit and sleeve attribution; named owners and approved environment |
| Historical/paper/live gates | Blocked | Qualified historical/corporate actions/strategies, separate 60-session paper authorization, broker/security and separate live permission |

Next work can address runtime adapters and production-readiness evidence, but unresolved policy values, real trusted sources and role assignments cannot be supplied by blanket approval. Full v1.1 completion remains blocked by those inputs. No production trading permission is granted by this qualification.

Research cap remains **$1,000**; production funding planned/unconfirmed; execution flags disabled. API/broker/strategies/historical/OOS evidence unchanged; 2026 OOS sealed; forward paper **0/60**. Only the disposable test database was stopped/restarted.
