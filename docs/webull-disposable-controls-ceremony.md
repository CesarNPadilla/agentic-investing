# Disposable passkey and guardian controls ceremony

The owner explicitly chose **A clearly labeled disposable controls-test review (recommended)**. This is a real passkey signature over test evidence, using a synthetic account and plan. It does not approve a Webull reset, trading, funding or trial launch.

The signed envelope uses schema `webull-disposable-controls-review-v1`, action `REVIEW_DISPOSABLE_CONTROLS_TEST_ONLY`, purpose `WEBULL_DISPOSABLE_CONTROLS_TEST_ONLY` and a separate `WEBULL_DISPOSABLE_CONTROLS_REVIEW_V1` challenge domain. Schema/action pairs must match. Test evidence cannot be verified as a reset-precondition review. The real-review schema/domain remain unchanged.

| Scoped step | Complete |
| --- | --- |
| Explicit test-purpose selection | 100% |
| Ceremony engineering | 100% |
| Protected package installation/audit | 100% |
| Local ceremony preparation | 100% |
| Actual integrated owner/guardian ceremony | 100% |
| Trial launch | 0% |

Ninety ceremony/signature/guarded-retention tests and 49 regression/native tests pass in distinct batches. The installed package audits 706 payload hashes and 812 exact protected objects. Wrapper syntax, installed import, fresh protected context/layout and bootstrap compilation pass. Both accounts remain disabled after preparation; no listener or process ceremony started.

## Completed owner action (historical; do not repeat)

Have your browser ready. In elevated 64-bit owner PowerShell run:

```powershell
& 'C:\Users\cesar\OneDrive\AI\agentic-investing\scripts\test_webull_disposable_controls_ceremony.ps1'
```

Enter your **AgenticGuardian password locally**. When prompted, open **http://localhost:8767** yourself, refresh if necessary, confirm the page says **SYNTHETIC ACCOUNT AND PLAN**, then select **Sign this disposable test with Windows Hello / passkey**. Complete your own authenticator prompt within 40 seconds. Do not share passwords, PINs or private passkey material. The agent must not operate your authenticator ceremony.

The owner process must have the actual standard desktop token. Both sides verify the fixed protected accepted credential record and fresh configuration. The guardian waits at most 45 seconds for a context-bound readiness marker emitted only after assertion verification. It then starts a job-supervised 15-second host; each pipe phase retains its five-second bound. This avoids starting the pipe deadline while you are still completing Windows Hello. Native server/client identity checks occur before payload exchange. Order is verified assertion â†’ guardian intent â†’ owner journal consumption â†’ guardian confirmation. The listener closes and the guardian account is disabled in cleanup. No persistent service is installed.

A failure retains all partial state, markers and diagnostics. Do not delete or replay contexts. Each invocation prepares a fresh context; a failed intent/consumption must be inspected before any operational recovery. A successful wrapper is still subject to independent inspection of the actual signed receipt, domain/purpose, journal, guardian intent/confirmation, closed listener, zero active job processes, hashes and ACLs.

## Exact test blueprints

These canonical JSON objects are digest-bound in the signed envelope. No actual brokerage account or economic reset plan is represented:

```json
{
  "account": {
    "purpose": "DISPOSABLE_CONTROLS_TEST_ONLY",
    "account": "SYNTHETIC_NO_BROKER_ACCOUNT"
  },
  "plan": {
    "purpose": "DISPOSABLE_CONTROLS_TEST_ONLY",
    "operation": "PASSKEY_GUARDIAN_RETENTION_TEST",
    "reset_authorized": false,
    "execution_available": false,
    "trial_started": false
  }
}
```

Account blueprint SHA-256: `a54e8a1c283194dd74eed7a58551f3dfa67f113f67f66b87c8c654df4a18ddc6`.
Plan blueprint SHA-256: `48ad320cae7aa9553f2f41b9bececa2f1f705d943e0e0fae3435eb072f53225a`.

Provider status/accounting/gap evidence, protected history and current-key/revocation/rollback controls, clock/remote-host qualification and atomic reset admission remain separate gates. The month trial remains unstarted: trial launch 0%, forward evidence 0/60, overall readiness unquantified. Numerical policy, risk engine, broker execution, strategies and historical/OOS data are unchanged.


The actual ceremony is independently accepted in [verification evidence](examples/webull-sandbox/disposable-controls-ceremony-actual-verification.json). The password/passkey action above is complete; no rerun is needed. Continue with [remaining provider evidence](webull-provider-evidence-followup-1012.md) and the separate protected-history/runtime qualification gates.
