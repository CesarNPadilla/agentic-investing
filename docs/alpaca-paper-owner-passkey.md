# Separate owner passkey enrollment prototype

The [owner's exact authentication choice](examples/alpaca-paper-month/owner-authentication-decision.json) selects Windows Hello/passkey in a separate local app. The prototype runs on loopback at http://localhost:8766 and does not load brokerage credentials, access the paper ledger, clear latches, approve recovery, or submit orders.

Open the local page yourself, choose **Enroll my passkey**, complete the browser's Windows Hello/platform passkey prompt, then choose **Test my passkey**. Human interaction is required; the agent must not impersonate it. Enrollment stores public credential material outside the repository at `C:\Users\cesar\AppData\Local\AgenticInvesting\owner-passkey-enrollment.json`; a second enrollment cannot overwrite it. No real credential has been enrolled by the agent.

The server uses [Yubico's FIDO2 verifier](https://developers.yubico.com/python-fido2/API_Documentation/autoapi/fido2/server/index.html), requests a platform authenticator and required user verification, verifies the exact localhost origin and relying-party challenge, limits challenges to 120 seconds and consumes each challenge once. Actual browser/Windows Hello enrollment remains untested until the owner completes it. Platform preference and a user-verification flag alone do not certify a particular authenticator manufacturer or independently establish the declared owner's legal identity.

This is enrollment and authentication testing only. Initial owner bootstrap, private-file OS permissions, action-bound assertions, credential/counter lifecycle and an independently protected recovery authority still require qualification before reset permission. The app runs separately but currently shares the Windows user security boundary; it is not isolation against an agent with that user's filesystem privileges. It deliberately cannot convert a successful test into recovery authorization. The existing external-reset gate remains false.

To restart the prototype locally:

```powershell
.\.venv\Scripts\python.exe -m security.paper_owner_passkey --credential-file 'C:\Users\cesar\AppData\Local\AgenticInvesting\owner-passkey-enrollment.json'
```

Cryptographic fixtures verify registration and a signed assertion through the actual library, plus missing user verification, incorrect origins, expiry and replay rejection. Fixtures are not real owner enrollment. The paper service's failed startup journal and all latches remain untouched.

Latest: real enrollment and authentication are recorded. The [action-bound review](alpaca-paper-readonly-recovery-review.md) now adds a separate signing mode for the immutable read-only restart plan. The owner app continues to have no ledger or broker access and cannot itself apply the acknowledgement or release risk latches.
