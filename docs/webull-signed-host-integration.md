# Synthetic signed owner/guardian host integration

The prepared fixture uses one generated software key and fresh public configuration; it does not use Windows Hello or establish actual human approval. The private synthetic key is discarded after forming the test receipt. The owner process consumes that frozen synthetic signature through the real journal code. Guardian PREPARE/CONFIRM records remain separate from reset, recovery and trading permission.

The guardian supervisor loads externally pinned protected configuration under the configured guardian identity, starts its host child in a kill-on-close job before resume, and applies the 15-second execution bound. The host handles two ordered single-use native pipes. The actual non-admin owner process verifies its token, authenticates each pipe server before sending, verifies the signature, requests PREPARE, consumes once in the owner-writable journal, then requests CONFIRM. Discovery includes fixture ID, action and envelope digest. Closed readiness bytes are renamed into place on Windows before publication; stale/mismatched discovery is rejected. Interruption retains state and no automatic retry or repair is offered.

Fifty-three related engineering tests passed for generated signature/discovery/identity rejection and the existing host/guarded-client/native app integration. The latter native integration uses injected role dispatch and synthetic signing; it does not qualify the actual cross-account fixture. Fifteen follow-up fixture/package tests passed after final source changes. Ruff passes. Installed-interpreter signature verification and bootstrap compilation passed.

The separate version-five package is installed at `C:\ProgramData\AgenticInvestingGuardian\Code\GuardianRelease-800ab34b3c240536`. Manifest SHA-256: `800ab34b3c240536017d8fc3fa8fcdb93e169fbacc47ef7f9933936f41d4c6ae`. All 697 payload hashes and 803 exact protected objects are audited; earlier packages are retained. Preparation creates fresh protected synthetic inputs and a separate layout, without credential entry, account enablement or host startup.

| Scoped step | Progress |
| --- | --- |
| Integrated fixture engineering checks | 100% |
| Protected package install/audit | 100% |
| Cross-account fixture preparation | 100% |
| Actual standard-owner/guardian signed host run (synthetic signature) | 100% |

## Completed local action

The following command completed successfully; no repeat is required:

```powershell
& 'C:\Users\cesar\OneDrive\AI\agentic-investing\scripts\test_webull_signed_host.ps1'
```

Enter the existing AgenticGuardian password locally. The wrapper uses the same-owner standard desktop token for the owner process; no owner password is requested. A current interactive standard desktop token is required. Each invocation creates a fresh five-minute synthetic context and layout. Expiry, missing discovery, connection ambiguity or any process failure blocks and retains diagnostics/state; do not delete or replay a retained context. The account is disabled again in cleanup. Successful receipts will need independent verification before progress is promoted.

This run is a bounded synthetic protocol fixture, not a deployed owner HTTP app or Windows service. A generated assertion is not evidence of a real owner passkey ceremony. Protected production provisioning/history, application/service lifecycle, clock qualification, remote-host denial, provider evidence and atomic reset admission remain separate gates. Both accounts are disabled at this checkpoint. Trial launch remains 0%, forward evidence 0/60 and overall readiness unquantified. No real owner approval, reset, broker order or live/paper trial is activated.

## Independent acceptance

Actual signed-host fixture accepted: receipt 58ca9e1d14134b5bbfe6986619db8fb6 independently verifies one cryptographically valid synthetic owner-journal consumption, matching guardian intent/confirmation, ordered PREPARE/CONFIRM terminal evidence, actual standard-owner process and zero remaining supervised job processes. Nine retained hash links, six exact protected ACLs, four guardian-owned records and clean diagnostics match; the 697-payload/803-object package remains audited and both accounts are disabled. Actual cross-account signed-host progress is 100% for this bounded software-signature fixture. Earlier 0% instructions are historical; no rerun is needed. Real Windows Hello owner signing, deployed owner app/service lifecycle, protected provisioning history, provider guarantees, clock qualification, remote-host denial and atomic reset admission remain pending. No real approval, reset or trading is activated. Trial launch remains 0%, forward evidence 0/60 and overall readiness unquantified.

The next engineering phase is the protected owner app and real passkey ceremony integration. A software-generated assertion cannot satisfy that gate. Any owner interaction must occur in the separate local app; do not share passwords or passkey material in chat.
