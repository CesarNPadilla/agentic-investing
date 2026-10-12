# Pinned owner-app integration

The owner UI now has a protected-context factory. It checks the configured Windows owner SID and non-elevated token before serving, then rechecks identity, held-handle ACLs, externally pinned configuration bytes, release binding, credential, journal and expiry for each context request. It uses the public credential and envelope in the pinned configuration. The existing unconfigured CLI remains unable to issue a challenge without guardian integration.

The factory requires an explicit exchange callback. A callable alone does not qualify transport or deployment; the cross-account fixture authenticates each guardian pipe before sending signed evidence. Filesystem protection retains the loader's administrator, prior writable mapping and rollback limitations. Outer process supervision remains required.

| Scoped step | Completed |
| --- | --- |
| Pinned app engineering and regression checks | 100% |
| Protected package installation and audit | 100% |
| Actual standard-owner construction/read-only context check | 100% |
| Actual cross-account HTTP signing fixture (synthetic) | 100% |
| Real Windows Hello app ceremony | 0% |
| Trial launch | 0% |

Thirty-two related tests passed, including actual loopback HTTP challenge/cookie/signature/confirmation and listener shutdown using synthetic signing and injected guardian dispatch. Ruff passes. Native standard-owner construction separately passed with eight retained hash links, six exact protected ACLs, clean diagnostics, unchanged empty journal and empty guardian reference directory independently verified. Both accounts remain disabled. No credential contents or brokerage data were read in this construction check.

Two fresh version-six packages are retained separately: construction package `93647e3ddacaff7de9ea18477db5b87a331bb18bdda98c89ca569fe10dda1e38` and HTTP fixture package `5eab9e9d45912101623c9fd9bed175fb06d6fb7e75f055d54914f5575cf46193`. Each audits 702 payload hashes and 808 protected objects. The second adds the HTTP test mode to the fixture driver; the earlier package is unchanged. Installed-interpreter HTTP/factory imports passed.

## Completed local action

This command completed successfully; no rerun is required:

```powershell
& 'C:\Users\cesar\OneDrive\AI\agentic-investing\scripts\test_webull_pinned_owner_http.ps1'
```

Enter the existing AgenticGuardian password locally. The agent cannot supply that password. The wrapper launches the actual standard-owner token and a bounded guardian host, creates a fresh synthetic context, and disables the guardian again. A standard owner desktop session and an unused localhost port 8767 are required. Do not reuse or delete retained contexts after failure. No earlier fixture needs repeating.

This test uses a pre-generated software assertion with a controlled test nonce inside the disposable fixture process. It opens its own loopback socket, performs HTTP review/begin/complete, then closes the listener. It is not a browser Windows Hello test or production entry point. No real owner approval, reset, broker order or month trial is authorized. Actual passkey interaction, application/service lifecycle, trusted provisioning history, provider contracts, clock qualification, remote-host denial and atomic reset admission remain separate gates. Overall trial readiness is not quantified.

## Startup-order correction

October 11 HTTP fixture correction: the reported c1a6735fb3bf4071af04aca6b8262c25 attempt failed closed with HTTP 403 while the guardian reached its five-second initial connection deadline. The retained terminal has no completed actions; the owner journal is empty and intent/confirmation are absent. Both accounts are disabled. Startup now uses a bounded ten-second pre-host readiness wait: the owner completes HTTP startup and challenge preparation, atomically publishes a context-bound marker, and only then the guardian starts the supervised host. Existing five-second pipe and fifteen-second child-job deadlines are unchanged. Eleven fixture tests and eight HTTP/host follow-up tests passed (overlapping batches); Ruff passes. The new 069895024e135b302535e931cf574caca99c62aae31724d367aded09c4a06c8c package audits 702 payload hashes/808 protected objects. Preparation is 100%; actual cross-account HTTP verification remains 0% pending the local guardian password. Earlier successful stages need no rerun. Trial launch remains 0%; no real passkey, reset or trading is activated.

Use the same command above. Each invocation creates a fresh context; the failed context remains blocked and must not be replayed. The owner readiness marker coordinates this synthetic test only and is not proof of human approval or provider evidence.

## Independent acceptance

Actual cross-account synthetic HTTP fixture accepted: receipt 98bfe742735e48ac832023bf06511086 independently verifies HTTP challenge/cookie/signature processing under the actual standard owner, exactly one cryptographically valid journal consumption, matching guardian intent/confirmation and ordered PREPARE/CONFIRM terminal evidence. Nine retained hash links, six exact protected ACLs, four guardian-owned records, context-bound readiness and clean diagnostics match. The supervised job reports zero processes; the HTTP close receipt and closed loopback port are verified. The 702-payload/808-object package remains audited and both accounts are disabled. Actual cross-account HTTP progress is 100% for this software-signature/controlled-nonce fixture. Earlier 0% retry instructions are historical; no rerun is needed. Real owner passkey ceremony, deployed app/service lifecycle, protected provisioning history, provider contracts, clock/remote-host qualification and atomic reset admission remain pending. No real approval, reset, broker order or trial is activated. Trial launch remains 0%, forward evidence 0/60 and overall readiness unquantified.

Next engineering scope: bind the real enrolled public credential and immutable review context to the protected owner app, and qualify its challenge-to-guardian lifecycle. A real Windows Hello interaction must be performed by the owner in that app; a synthetic receipt cannot satisfy it. This successful test does not qualify a persistent service or reset admission.
