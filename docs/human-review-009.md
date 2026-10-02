# Phase v0.9 — human review

**Outcome:** isolated deterministic risk diagnostics implemented; no policy or execution authority changed. The [control inventory](risk-engine-readiness-v09.md) and [synthetic scenarios](examples/risk-diagnostics-v09/scenarios.json) are reviewable. The existing evaluator already checked cash, attributed $160 sleeve, allowlist, whole-share order format, open commitments, reconciliation, freshness when configured, kill switch, theses, and loss values when configured. The wrapper adds explicit quote timestamp, observed session state, duplicate proposal ID, technical-eligibility label, environment, impact fields, and replay digest. A complete passing fixture yields `REVIEW_REQUIRED`, never broker submission.

Undefined or incomplete: current-policy daily-loss hard stop/timezone, experiment loss limit, state age, hard position/concentration maxima, independent portfolio exposure cap, trusted trading clock and quote source, durable conflict reservation, and real broker reconciliation. The default policy fails closed. Fixture-only limits exist to exercise branches and do not authorize trading. A synthetic proposal above $160 is rejected deterministically. The proposed $1,000 scenario remains rejected against the unchanged $160 cap. Pending buys consume both cash and experimental capacity; existing nonallowlisted holdings remain in whole-portfolio exposure. Missing policy or price produces `missing_evidence` and no executable result. Identical inputs replay to identical decisions and audit IDs.

Technical eligibility is supplied separately. An ineligible signal is blocked before it could be mistaken for a risk acceptance; unknown eligibility is reported as not evaluated. H03's historical Risk Engine outcome remains `NOT_EXERCISED`. No v0.8 historical results were rerun or promoted.

The synthetic registry contains 24 scenarios with exact replay and versioned input/result digests. Full repository verification: **515 tests passed**, Ruff passed, and `git diff --check` passed. These checks did not exercise broker methods, real accounts, or 2026 OOS.

Before genuine paper validation, the user must decide the missing policy hard stops and limits, fund and classify any sleeve, approve a trusted data/session boundary and atomic reservations, and resolve historical evidence and corporate-action gates. Before human-approved live trading, broker security, idempotency, order/fill reconciliation, restart recovery, monitoring, and explicit live authorization need separate qualification. Synthetic passing tests alone establish neither readiness.

| Mandatory final state | v0.9 result |
| --- | --- |
| Original v1.0.0 strategies | UNCHANGED |
| H01 / H02 | EXPLORATORY CANDIDATE ONLY / DEFERRED_NOT_IMPLEMENTED_NOT_RUN |
| $1,000 / current policy cap | PROPOSAL_SIMULATION_ONLY / $160 UNCHANGED |
| Risk diagnostics | ISOLATED_SYNTHETIC_NO_BROKER_EXECUTION |
| Qualifying historical validation / both strategies | BLOCKED / NOT_ELIGIBLE |
| 2026 OOS / forward paper | SEALED / 0/60 |
| Paper / production execution / broker submissions | DISABLED / DISABLED / NONE |

Stop after v0.9 for human review. Do not begin v1.0 or change Investment Policy from this report.
