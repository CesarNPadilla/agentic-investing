# Owner enrollment verification and audit persistence

The owner reported "Done, please proceed." The private credential file exists and contains the enrollment recorded by the WebAuthn app. The [sanitized check](examples/alpaca-paper-month/owner-enrollment-check.json) records its actual enrollment timestamp and file digest without copying credential material. No legal-identity verification, recovery approval or trading permission is inferred.

The original prototype returned successful authentication tests to the browser but did not persist their signed evidence. Consequently the earlier test cannot be independently verified after the fact. This gap is now corrected: successful authentication tests save the original assertion, challenge state, credential digest and actual verification timestamp in separate, exclusively created files under the private `owner-passkey-verifications` folder. Failed or replayed challenges create no success receipt. These receipts prove authentication testing only, not a recovery action. Cryptographic fixture tests exercise the actual verifier and receipt creation/replay rejection.

Open http://localhost:8766 and select **Test my passkey** once more with the existing credential. Do not enroll again. A direct human Windows Hello/passkey operation is required to create real evidence; the agent cannot supply or invent it. The service's unfinished event journal is unchanged, and no latch is cleared by this test.

Action-bound recovery approval, credential lifecycle and the separately protected recovery authority still require implementation and qualification. The app continues to share the current Windows user's security boundary and remains an authentication prototype, not a qualified external reset service.

Follow-up: the owner completed the repeat test. [Real verification evidence](examples/alpaca-paper-month/owner-real-verification.json) records cryptographic re-verification of the privately retained signed assertion against the enrolled credential, with required user verification. No further repeat of this authentication test is requested. Its purpose remains authentication testing; it is not an action-bound recovery approval.
