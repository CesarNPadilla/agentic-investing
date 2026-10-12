# Clock decision and transport-health preparation

The owner explicitly selected Windows Time using time.windows.com and a maximum
reported clock-error bound of one second. The exact question and answer are in
clock-policy-decision.json, without an invented approver identity or decision
timestamp. The paper observer now reads that policy. The existing Windows peer
designation time.windows.com,0x9 is preserved; no source configuration changed.

A fresh status query showed stale synchronization. An authorized resync completed
successfully and cleared the stale/error diagnostics. Immediately afterward,
root dispersion plus half root delay was 7.9563316 seconds. Qualification therefore
still fails CLOCK_REPORTED_ERROR_BOUND. Command success is not clock qualification;
the one-second limit is not relaxed and the reported bound is not replaced by
the smaller phase offset. Further source/host investigation is required.

Transport-health preparation now binds each probe to an authenticated, subscribed
connection epoch and token. Matching responses require finite monotonic times
within five seconds; wrong, late or overlapping probes invalidate continuity.
Successful later probes cannot clear continuity loss. Reconnect starts without
health evidence. This state machine is not yet connected to actual websocket
ping/pong frames, and it never establishes a security's initial trading status.

Validation: 26 targeted tests passed for stream health, status handling, stream
subscription probe, observer failures, and daily-loss persistence. Lint and
whitespace checks passed. Current policy and evidence JSON source digests validate.

Readiness remains 22/36 (61%). The clock-policy choice is resolved; actual clock
qualification remains blocked. Other launch blockers include initial market
status, coherent snapshot/activity cutoffs, midnight equity source qualification,
authenticated reset, continuous event/timer monitoring and recovery, and actual
paper broker acceptance. The trial has not started and execution remains disabled.
