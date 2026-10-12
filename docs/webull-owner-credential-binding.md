# Owner review credential binding

The completed localhost:8768 authentication diagnostic proves possession/user verification for the observed credential. It does not authorize adopting that credential for Webull reviews. This separate ceremony asks the owner to authorize the displayed candidate public key for future owner-review signing.

The binding profile uses localhost:8769, a distinct `WEBULL_OWNER_REVIEW_CREDENTIAL_BINDING_ONLY_V1` challenge domain and an externally pinned candidate fingerprint. Its protected configuration binds the credential, Windows roles, installed release and fresh five-minute context. Wrong candidate pins, modified configuration, wrong origin, expiry and replay fail closed. Diagnostic assertions cannot authorize binding. Neither profile reads or writes a review journal or calls a guardian/broker.

Candidate public credential SHA-256:
`fc0761142d56f020eac42868d377fb12849458e90a6db5c23edc9bc6ca58e22b`

The candidate comes from the existing enrollment snapshot, independently checked against the completed authentication evidence. The original owner-writable enrollment is not treated as authoritative identity or adoption evidence. This ceremony records explicit adoption intent, not legal identity attestation or proof of an authenticator manufacturer. The approved Windows owner/guardian role expectations are supplied by deployment, not enrollment declarations or HTTP input.

| Scoped step | Complete |
| --- | --- |
| Credential-binding engineering | 100% |
| Protected package installation/audit | 100% |
| Owner ceremony preparation | 100% |
| Actual owner binding ceremony | 100% |
| Protected accepted credential registry installation | 100% |
| Real Webull review/app/guardian lifecycle | 0% |
| Trial launch | 0% |

Seventeen related tests passed. Five binding follow-up tests passed including the added changed-candidate case; these batches overlap. Ruff, UI JavaScript syntax, installed-profile import and protected bootstrap compilation pass. The separate version-eight package `ceaece1e23febc153bdb8d1a3db2e575db3471397713cb027e23e8fd736f8fc7` audits 704 payload hashes and 810 exact protected objects. Earlier packages, completed diagnostic evidence and failed contexts remain intact. Both accounts remain disabled; preparation started no listener and performed no passkey operation.

## Completed owner action (historical instructions; do not repeat)

Have a browser ready, then run in elevated 64-bit owner PowerShell:

```powershell
& 'C:\Users\cesar\OneDrive\AI\agentic-investing\scripts\test_webull_owner_credential_binding.ps1'
```

Open [the local binding page](http://localhost:8769), refresh once the page is available, confirm the displayed public credential fingerprint, and select **Bind this credential with Windows Hello / passkey**. Complete the authenticator prompt yourself. The agent must not perform this ceremony for you. No guardian password is requested. Do not share your PIN, password or private passkey material in chat.

The listener waits at most 40 seconds; an issued challenge expires after 30 seconds. A fresh invocation creates a new context after an expired/failed attempt; do not replay or delete retained contexts. Port 8769 must be unused and a same-owner standard desktop session must be available. Success retains signed binding evidence and closes the listener. The empty disposable review journal and guardian directory stay unchanged, and both accounts stay disabled.

After the owner action, independently verify the signature, binding domain, candidate fingerprint, configuration/roles and receipt hashes before installing a separately protected accepted credential registry. That installation has not happened. Binding evidence does not itself configure a real Webull review plan or grant guardian, reset, funding, environment, paper or live permission. Application/service lifecycle, protected history/rollback, trusted provider/accounting/halt/session evidence and atomic reset admission remain separate gates. Trial launch stays 0%, forward evidence 0/60 and overall readiness unquantified.


Binding is independently accepted in [actual verification](examples/webull-sandbox/owner-credential-binding-actual-verification.json). The protected record is now installed. Continue with the [guardian registry check](webull-owner-credential-registry.md); the original owner-action instructions above are historical. Actual app/guardian use, active selection and rollback/revocation remain separate gates.
