# Policy v0.2 Phase 2 gap analysis

Inspection date: 2026-09-29. Sources: codex-handoff.md, roadmap.md, architecture.md,
investment-policy-v0.2.md and the actual API/domain/persistence implementation.
The starting working tree was clean. This is an incremental foundation pass, not a rewrite.

| Policy area | State before this pass | Outcome / remaining gap |
| --- | --- | --- |
| Configurable InvestmentPolicy | v4 model, v0.2 JSON/schema, Python injection | Added explicit startup JSON-file loading with fail-closed errors |
| Holdings / research / purchase scopes | Implemented independently | Preserved; existing holdings never imply purchase authorization |
| $160 experimental budget | Explicit attributed quantities, costs and orders | Preserved; existing portfolio value is uncapped by this budget |
| Broker accounts/positions/cash/orders/history | Authenticated read adapter and normalized evidence | Preserved unchanged; non-atomic and incomplete share/settlement evidence remains explicit |
| Whole-portfolio analytics | Values, P/L, allocation, concentration, sleeves, themes, correlations, benchmark evidence | Preserved; live reference feeds, ETF look-through and FX remain pending |
| Incremental analysis evidence | Omitted request fields reset prior evidence | Fixed: omission inherits; explicit null/empty clears; derived records retain parent links |
| Position theses / review history | Versioned persistence; API returned latest only | Added authenticated, ordered, bounded revision-history reads |
| UNKNOWN original rationale / registry | Implemented | Preserved; owner rationale and individual targets are still unspecified |
| News -> thesis review | Persistent nonexecuting requests, quarterly strategic checks | Preserved; live provider, scheduling and request-completion workflow pending |
| Long-term / swing / TradeProposal / Risk | Separate interfaces and deterministic checks | Preserved; no new signals, execution, or approval bypass |
| Loss / kill switch / human approval | Required checks, explicit UNSET controls | Preserved; owner must define missing loss/freshness controls |
| Operational persistence | Additive tables; SQLite tests | Versioned migrations, PostgreSQL concurrency, retention and backup/restore remain pending |
| Forward strategy validation | Evidence interfaces and separate qualification service | Real 60-session non-synthetic evidence remains pending; never grants execution permission |

## Decisions made in this pass

See ADR-015. Policy selection belongs at application composition/startup. It is never
controlled by news, proposals, broker responses or analysis payloads. No runtime policy-write
endpoint is added. Explicit configuration errors do not fall back to permissive defaults.

Enrichment is incremental within one immutable observation lineage. It does not copy evidence
automatically across fresh broker snapshots, change timestamps, or certify reference quality.
Current configured policy still evaluates newly derived analysis; prior records retain their
original policy. Explicit clearing remains possible and restores unknown/fail-closed results.

Thesis history is read from retained revisions with account/symbol filters and cursor-style
pagination. It requires the existing dedicated bearer token and never loads the broker.
The token continues to authorize application-wide portfolio reads, not per-account tenancy.

## Human decisions and next development task

No new investment values were assumed. Keep the current AAPL/MSFT/SPY purchase allowlist until
explicitly changed. Loss limits, freshness tolerance/day boundary, experimental attribution,
individual targets/current theses and swing controls still require owner decisions.

Recommended next task: implement an authenticated, source-identified complete-ledger import
workflow with provenance and reconciliation against existing broker observations. Begin with
synthetic settlement, transfer, corporate-action and partial-fill fixtures; preserve unknowns
and do not infer the quantities missing from Webull cash activities. Keep it entirely read-only.
Operational migrations and database restore tests should precede storing production evidence.
