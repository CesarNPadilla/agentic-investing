# Risk Engine readiness v0.9

The existing `risk.evaluator.evaluate` is a pure hypothetical review. It reconciles a complete portfolio ledger, enforces the current $160 attributed experimental sleeve, settled cash after open-buy reservations, whole-share allowed BUY LIMIT/DAY/CORE orders, no leverage, fresh state when an age limit exists, kill switch, theses, and configured daily and experiment loss stops. A passing result is `REQUIRE_HUMAN_REVIEW`; execution remains unavailable. The v0.9 wrapper in `risk/diagnostic_harness.py` adds explicit quote timestamp, observed session state, proposal ID, environment, and deterministic diagnostic audit fields. It has no broker imports.

| Control | Classification | Basis or gap |
| --- | --- | --- |
| Maximum position size | POLICY_UNDEFINED | Optional `max_position_exposure` unset in current policy; diagnostic enforcement exists when set. |
| Single-security concentration | PARTIAL | Measured and warned; optional hard maximum unset. |
| Maximum portfolio exposure | PARTIAL | No-leverage ceiling versus reconciled equity exists; independent maximum exposure value absent. |
| Available cash | IMPLEMENTED_AND_TESTED | Settled cash less open-buy commitments; buying power is an additional ceiling. |
| Experimental-capital limit | IMPLEMENTED_AND_TESTED | Attributed cost and pending orders plus proposal must fit $160. |
| Allowed securities | IMPLEMENTED_AND_TESTED | AAPL/MSFT/SPY purchase allowlist; existing other holdings remain visible. |
| Allowed order types | IMPLEMENTED_AND_TESTED | Whole-share BUY LIMIT/DAY/CORE only in hypothetical evaluation. |
| Trading-session restrictions | PARTIAL | Order session flag checked; v0.9 explicit observed core-session input; trusted exchange clock integration absent. |
| Daily realized/unrealized loss | POLICY_UNDEFINED | Flow-adjusted P&L check exists but authorized hard stop and timezone are unset. |
| Duplicate/conflicting orders | PARTIAL | v0.9 exact proposal-ID duplicate check; no durable cross-process conflict reservation for concurrent proposals. |
| Existing positions and pending orders | IMPLEMENTED_AND_TESTED | Reconciliation and attributed inventory; pending commitments count against cash and cap. |
| Kill switch | IMPLEMENTED_AND_TESTED | Fresh, explicitly disengaged state required. |
| Missing/stale market data | PARTIAL | Position marks and v0.9 reference quote checked; trusted quote provenance/live boundary absent. |
| Missing policy values | IMPLEMENTED_AND_TESTED | Critical unset controls fail closed; optional limits need human definition. |
| Environment isolation | PARTIAL | Diagnostic harness refuses non-research input; evaluator permits production *read data* in research; operational separation remains unproven. |

The fixture-only policy defines $10 daily loss, $20 experiment loss, 120-second age, and UTC to exercise passing and failing branches. It is not the authorized policy. The default policy remains fail closed. Synthetic tests cannot establish broker reconciliation, idempotency, durable reservations, clock accuracy, or production readiness.
