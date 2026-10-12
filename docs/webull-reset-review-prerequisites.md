# Webull staged reset-review prerequisites

`security/webull_reset_review.py` evaluates synthetic controller-selected evidence without importing a broker, opening a journal or changing any latch. This extends the untrusted request parser; it does not change executable risk policy or deploy a controller.

The review digest binds the action, request identifier/account/expected state, current account/state/policy, designated credential, breach New York day, latch reasons, reconciliation timestamp/state and source flags, and exact published calendar digest. A changed policy, state, calendar or request invalidates the old review. Runtime-provided usernames and approval flags remain forbidden by the existing wire parser.

The checker derives the earliest next trading day from the existing reviewed NYSE calendar. It requires that day to have arrived and the current New York day to be a scheduled trading day; unknown coverage blocks. The schedule is not halt evidence, proof of an extraordinary-closure check or trading permission. Synthetic calendar-source qualification is a fixture input, not a production qualification claim.

Fresh reconciliation must be complete, match current state, be on the current New York day and be no more than 60 seconds old. Approval must follow reconciliation, not be future-dated, match the exact review/credential, carry the synthetic external-verifier flag and be less than 300 seconds old. The five-minute boundary matches the existing approved N10 check; the 60-second reconciliation freshness matches the existing synthetic reset preconditions. Neither numerical rule nor the approved next-day/reconciliation/approval ordering is changed.

Only ACCOUNT_DAILY_LOSS and SLEEVE_DAILY_LOSS latch reasons are eligible. An empty latch set, cumulative/other independent latch, independent stop, unknown provider contract or missing approval blocks. A supplied set of already-used approval identifiers rejects replay; this does not consume identifiers or qualify a durable/atomic approval counter.

All context and approval models explicitly require SYNTHETIC_ONLY. Boolean signature/source inputs are fixture declarations, not cryptographic signatures or trusted source attestations. This checker is not exposed as a runtime endpoint, connected to the native pipe or adopted into executable risk policy. Even when every synthetic prerequisite passes, production-owner verification, approval consumption, controller admission, reset, execution and trial startup remain false.

Twenty-two tests cover complete synthetic ordering without authority; changed account/state/policy/calendar/request bindings; absent/ineligible latches; same-day, weekend and out-of-coverage resets; stale/future/mismatched reconciliation; source and independent stops; missing/wrong-owner/unverified/expired/out-of-order approval; replay and schema/clock failures. The source-unknown case remains blocked even with a fully formed synthetic owner approval.

The prerequisite implementation/targeted verification batch is 2/2 (100%). Protected service deployment, real action-bound passkey verification, durable approval consumption, crash/rollback recovery, source contracts and actual remote-host denial remain unqualified. Overall Webull readiness has no accepted numerical percentage; trial launch stays 0%, forward evidence 0/60 and live permission absent. No new password fixture or signing action is required for this staged check.

Continuation: [review-only cryptographic verification and retention](webull-owner-review-evidence.md) are implemented and tested with synthetic keys. They do not consume actual reset approvals or replace this checker's synthetic signature/source inputs. Real owner signing and protected deployment/recovery remain unqualified.
