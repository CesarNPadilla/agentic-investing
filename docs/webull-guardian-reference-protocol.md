# Webull guardian: staged reference protocol

Guardian provisioning is complete. The next implementation batch now passes 20 synthetic tests: a bounded request parser, separate reference writer and native identity bridge. These modules are staged in the repository; the pinned installed review source/environment are unchanged. No guardian service, pipe session or real reference is deployed.

**Verification follow-up:** the owner completed the dummy-file fixture. Independent inspection matched the retained child to current source, verified five dummy contents and empty diagnostics, and confirmed both accounts disabled. This batch is now 3/3 (100%); no repeated password entry is needed for it. The standard-owner desktop-token check also passes: 37 denied directory mutation/deletion handles and six successful read controls. It duplicates an existing same-owner, non-elevated Explorer token at SecurityImpersonation level, verifies the effective non-admin identity, performs handle opens only, restores elevation and verifies unchanged directory descriptors. This is a scoped token check, not a deployed owner-app process test. The initial linked-token attempt failed with invalid impersonation level and did not qualify any access; the successful implementation uses the independently checked desktop token.

The staged `GuardianRequestPipe` now routes bounded frames to guardian-specific identity/receipt dispatch, using the server clock. It reuses the first-instance, local-only pipe, exact security readback, five-second connect/read deadline and close-on-failure path. Six new dispatch/framing tests plus existing native transport and guardian protocol regressions pass (36 total). New tests inject transport/dispatch; they do not establish actual owner-to-guardian cross-account operation, remote-host rejection or service lifecycle. No installed release changed.

The owner app sends `PREPARE_REVIEW_REFERENCE` with the original signed review receipt, canonical request ID and exact envelope digest. The guardian verifies the signature and current review window, reads the cryptographically verified owner journal without writing it, and exclusively writes/fsyncs an intent. Existing or partial intent evidence blocks another preparation. The owner app then consumes the receipt in its own journal. A distinct `CONFIRM_REVIEW_CONSUMPTION` request lets the guardian read that journal again, require exactly the matching signed receipt and ordered consumption time, and exclusively retain confirmation. Confirmation grants no reset, recovery or execution authority.

The parser accepts at most 4,096 bytes and rejects duplicate keys, nonfinite JSON, unknown fields, caller identity/path claims and incorrect context. The bridge requires the configured guardian process identity and identifies the connected owner through native pipe impersonation, reverting before persistence. Its tests use an injected identity API; actual guardian transport, bounded framing/deadlines and deployment remain pending. The existing runtime registration pipe has a different protocol and is not a deployed guardian endpoint.

Tests cover invalid/expired signatures, replay, concurrent preparation, confirmation before consumption, deleted journal consumption, modified intent, future consumption and wrong caller/process identities. Guardian reference integrity depends on the qualified separate writer and ACL boundary. These tests do not establish protection against a compromised guardian, joint reference/journal rollback, host power loss or a service lifecycle. The protocol is not yet integrated with the installed owner app.

## Next owner-run check

The following command is historical preparation and is now complete. Do not rerun it. Next engineering work is a separately pinned guardian execution package, actual cross-identity transport and lifecycle qualification, then integration with owner review state. Provider evidence remains independently required.

The bounded dummy-file fixture is prepared and its wrapper and embedded child both parse successfully. Preparation is 2/3 (67%): implementation and syntax verification complete; actual guardian-token execution/receipt inspection pending. This percentage describes this fixture only. Actual token qualification is pending.

Run in elevated 64-bit PowerShell:

```powershell
& 'C:\Users\cesar\OneDrive\AI\agentic-investing\scripts\test_webull_guardian_access.ps1'
```

Enter the **AgenticGuardian password chosen during provisioning** locally. This is not the paper runtime password, broker password or Windows Hello PIN. Do not share it here. Engineering cannot supply this owner-held password, so direct local entry is needed for the actual identity check.

Both accounts must start disabled. The script temporarily enables only AgenticGuardian, launches a hidden child under that account, checks dummy reads/write denial in Code/Config and dummy writes in References/Receipts/Logs, and disables the guardian in `finally`. It retains dummy fixtures, diagnostics and a result path for independent inspection. No credentials, real journal/reference, broker calls, pipe session or service are used. A host crash or forced wrapper termination can interrupt cleanup; inspect account state in that case.

Passing this check establishes five bounded dummy-file operations under the actual guardian token. Standard-owner deletion denial, directory escalation, authenticated guardian transport, lifecycle, protected code deployment, actual signing/reset and provider contracts still need qualification. Do not rerun provisioning or the completed runtime fixtures.

Trial launch remains 0%; forward evidence remains 0/60. Overall Webull readiness has no accepted percentage. Trading stays disabled. The [Webull provider questions](webull-provider-evidence-questions.md) remain a separate dependency.
