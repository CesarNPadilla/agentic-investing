# Event observer crash and source-failure audit

Two gaps were corrected in the read-only event observer. A risk diagnostic that
failed to observe the account could previously be marked completed before the
controller stopped. Completion now requires a successful account observation
and no observation deadline failure. Risk blockers still remain visible; a
technically completed read is not trading admission.

On startup, the controller now rejects any unfinished event-check record in
the account-bound durable journal. This covers a crash after the journal claim
but before diagnostic completion, as well as failed source reads. No automatic
claim deletion, reset, or latch release was added. Separate read-only tools may
help investigate; they do not clear an unfinished record or restart authority.

Validation: 18 targeted event, timeout, trade-stream and observer tests passed.
New cases cover crash-after-claim restart refusal and source failures remaining
incomplete. Lint, JSON source digests, private journal integrity and git diff
whitespace checks passed. No new real broker mutation or process deployment was
performed.

Readiness remains 23/36 (64%). Persistent supervision and independent timer
enforcement remain unqualified. Initial trading status, publication/snapshot
coherence, daily-flow qualification, authenticated resets and actual broker paper
round-trip acceptance still block launch. The Nasdaq supplemental-source question
remains pending; a general request to proceed does not select a risk data source.
The month trial remains unstarted and live execution disabled.
