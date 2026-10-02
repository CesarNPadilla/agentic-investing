# Live execution safety checklist v0.9

Paper and production execution are **DISABLED**. The synthetic diagnostic tests establish no execution readiness.

| Safeguard | Current assessment |
| --- | --- |
| Secret management and least privilege | Existing local credential isolation; production write permissions and rotation not qualified. |
| Separate research, paper, live environments | Research/paper policy distinction exists; enforceable deployment and credential boundaries not qualified. |
| Explicit live authorization and human approval | Human approval required; no live authorization. |
| Immutable audit logging | Research/evaluation digests exist; end-to-end external order audit not qualified. |
| Broker reconciliation and order-status recovery | Read-side reconciliation exists; real fill/status/restart recovery not qualified. |
| Order idempotency and atomic reservations | Synthetic workflow tests exist; real concurrent broker path not qualified. |
| Stale data and trusted trading hours | Fail-closed checks exist; authoritative market clock/quote boundary absent. |
| Kill switch | Deterministic check exists; operational end-to-end kill test pending. |
| Daily loss, exposure, position, concentration limits | Daily hard stop and several maximums unset in authorized policy. |
| Securities and order types | Buy allowlist and order restrictions implemented in hypothetical evaluator. |
| Monitoring, notifications, failures | Operational incident response and alert delivery not qualified. |
| Broker API limits | Rate, partial fill, reject, outage, and cancel behavior not qualified. |
| Home Lab credential isolation | Future deployment review required; no diagnostic fixture contains credentials. |

Genuine paper validation additionally requires qualifying historical gates, complete corporate-action and historical knowledge evidence, explicit policy controls, trusted data/session inputs, tested reconciliation and reservations, and separate approval to start the 60-session clock. Human-approved live trading requires a further explicit authorization and broker integration/security review. Limited automation is a separate future policy decision.
