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
| [ADR-019](adr-019.md) | Two immutable research hypotheses, preregistered periods, durable OOS exposure and limited sensitivity | Strategy Experiment Lab v0.1; synthetic results NOT_ELIGIBLE |
| ADR-020 | Separate historical price, fundamental, action and calendar providers; require proven publication and revision vintages through an auditable knowledge boundary | Research-only implementation; FMP qualification FAIL (HTTP 402), 2026 OOS sealed |
| ADR-021 | SEC EDGAR accession-scoped submissions/XBRL as primary historical fundamental candidate; preserve amendments and reject unproven original vintages | v0.3 conditional reconstruction, qualifying strategy validation blocked |
| ADR-022 | Keep corporate-action economic effects separate from historical signal availability; version events, reconcile source terms, and gate complete accounting independently | v0.5 bounded diagnostic implemented; accounting and signal qualification blocked |
| ADR-023 | Isolate current-vintage retrospective diagnostics in an explicit nonpromotable evidence class with sealed 2026 OOS | v0.6 implemented; qualifying validation blocked, paper 0/60, execution disabled |
| [ADR-024](adr-024.md) | Preregister isolated exploratory swing design questions before implementation; retain v1.0.0 baseline and classify 2025 as research-informed | v0.7 design proposal, awaiting human review; no candidate run |
| [ADR-025](adr-025.md) | Execute only human-scoped H01/H03/H04 and $1,000 counterfactual feasibility as isolated, nonpromotable research; defer H02 | v0.8 completed; no policy or execution change |
| [ADR-026](adr-026.md) | Wrap the existing deterministic policy evaluator with synthetic-only diagnostics and immutable input/result digests | v0.9; no broker or policy change |
| [ADR-027](adr-027.md) | Specify future capital/loss/exposure policy as explicitly unapproved, nonexecutable evidence; keep account and sleeve stops distinct | v1.0 design awaiting human approval |
| [ADR-028](adr-028.md) | Separate each risk-policy decision, funding, implementation, paper and live authorization in a source-digested pending register | v1.0.1 decision package; no approvals recorded |
| [ADR-029](adr-029.md) | Reconcile ten explicit numerical design approvals with user-message provenance; keep all separate authorizations pending | v1.0.2 complete; 10 approved / 25 pending; inactive |
| [ADR-030](adr-030.md) | Record blanket proposal approvals separately from missing concrete inputs and operational readiness | v1.0.3; 35 approved responses; unresolved prerequisites; inactive |
| [ADR-031](adr-031.md) | Start independent approved sleeve checks in an isolated synthetic v1.1 foundation | v1.1a complete; no runtime integration or execution |
| [ADR-032](adr-032.md) | Persist isolated synthetic sleeve diagnostics with sticky latching and fail-closed replay | v1.1b complete; SQLite foundation only; no operational reset |
| [ADR-033](adr-033.md) | Reserve isolated synthetic cash/sleeve capacity atomically through partial/terminal lifecycle | v1.1c complete; PostgreSQL and cross-control integration pending |
| [ADR-034](adr-034.md) | Qualify atomic synthetic risk/latch/reservations under PostgreSQL SERIALIZABLE transactions | v1.1d complete; bounded synthetic qualification, runtime integration pending |
| [ADR-035](adr-035.md) | Bind synthetic evidence/session qualification and review expiry before atomic reservation | v1.1e complete; real source trust/human authentication pending |

ADR-005 now includes deterministic hypothetical investment-policy checks and portfolio
intelligence; no production execution is enabled. ADR-006 preserves separate read-source
environments and research/paper policy; production account reads do not authorize trading.

Capital amendment: [revision 0.3](capital-cap-change-v03.md) implements the explicitly requested $1,000 local research cap through versioned configuration. Production funding remains planned; no production execution permission or deposit confirmation is inferred.
