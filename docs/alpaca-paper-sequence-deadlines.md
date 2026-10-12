# Paper plumbing sequence and observation deadlines

The frozen PAPER_CONTROL_PLUMBING 1.1.0 sequence adds intent-only exits and
re-entry to the unchanged 1.0.0 entry sizing. It permits one entry per New York
trading session, exits only reconciled strategy-owned shares after the entry
order is terminal, and blocks unresolved orders. Foreign holdings are retained
for review. Exits retain the $25 minimum and the paper protocol's $100 maximum;
a position outside those bounds requires review rather than an exception.
Trial end blocks intents and reports the remaining holdings for human review.
Stable account/version/session/side identifiers support recovery, but the caller
must persist and reconcile the session and owned-fill state before admission.

A separate bounded observation dispatcher returns a blocked report and calls a
supplied latch callback within the configured deadline while a reader is stuck.
Late results are discarded. A blocked Python thread cannot be cancelled; service
recovery is mandatory before further dispatch. This helper is not yet connected
to the real observer or order runner and does not qualify the event/timer gate.

Readiness remains **21/36 (58%)**. No new acceptance criterion is claimed until
durable sequence integration and the independent runtime watchdog are verified.
The previous v3 evidence snapshot is preserved. Paper orders and the month trial
have not started, and live execution remains disabled.

Remaining launch blockers include clock-policy approval and a qualified clock,
initial trading-status/stream-health evidence, coherent ledger/snapshot cutoffs,
daily baseline and authenticated reset integration, full runner recovery, and
controlled paper broker acceptance. General instructions to continue do not
choose the outstanding clock-error tolerance.
