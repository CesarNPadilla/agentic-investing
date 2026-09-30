# Architecture decision log

Recorded 2026-09-28. ADR-001 through ADR-007 carry forward the accepted architecture discussion.

| ID | Decision | Status |
| --- | --- | --- |
| ADR-001 | Python primary backend; FastAPI HTTP API | Accepted |
| ADR-002 | PostgreSQL system of record | Accepted |
| [ADR-003](adr-003.md) | Broker-independent adapters and normalized domain models | Synthetic read-only foundation implemented and tested |
| ADR-004 | LLM cannot directly execute broker orders | Accepted |
| ADR-005 | Deterministic risk controls outside agents | Accepted |
| ADR-006 | Separate paper and live environments | Accepted; future phases |
| ADR-007 | Home Lab initially research/paper infrastructure only | Accepted |
| ADR-008 | Structured Pydantic research outputs with provenance and missing-data markers | Implemented foundation |
| ADR-009 | Synthetic provider and disabled LLM are initial defaults | Implemented foundation |
| ADR-010 | SQLite local fallback; PostgreSQL Docker deployment | Implemented; PostgreSQL startup, report storage, and restart persistence verified |
| ADR-011 | Broker contract is read-only; no execution contract in Phase 1 | Implemented foundation |
| ADR-012 | OneDrive project source; environment and active local data outside sync | Implemented setup guidance |
| [ADR-013](adr-013.md) | Separate holdings, research universe, purchase allowlist and experimental capital; read-only reconciliation and position theses | Implemented; broker evidence gaps explicitly retained |
| [ADR-014](adr-014.md) | Investment Policy v0.2: thesis-led research, sleeve monitoring, isolated strategy interfaces and nonexecuting risk reviews | Implemented; no execution authorization |
| [ADR-015](adr-015.md) | Startup policy loading, incremental immutable analysis evidence and authenticated thesis revision history | Implemented; no broker changes |
| [ADR-016](adr-016.md) | Evidence-grounded long-term research, atomic assessment/thesis audit and targeted reviews | Research-only v0.1; no execution capability |
| [ADR-017](adr-017.md) | Persistent opportunities, separate versioned strategies, point-in-time indicators and independent proposal risk review | Research-only v0.1; execution disabled |
| [ADR-018](adr-018.md) | Offline point-in-time shared-strategy backtesting, corporate-action accounting, immutable experiments and fail-closed validation | v0.1; no paper or live broker execution |

ADR-005 now includes deterministic hypothetical investment-policy checks and portfolio
intelligence; no production execution is enabled. ADR-006 preserves separate read-source
environments and research/paper policy; production account reads do not authorize trading.
