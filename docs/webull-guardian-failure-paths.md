# Guardian native failure paths

Four installed-code integration checks pass under the engineering identity: no client, a truncated frame, an oversized frame and a caller whose real Windows SID differs from the configured owner. Each fails closed, closes the pipe, leaves no thread impersonation token and never reaches the reference handler. The no-client and truncated-frame checks finish at their configured deadlines; frame and caller rejection happen immediately after reception. Client sent-frame controls distinguish a real partial/invalid message from a client that never connected.

This engineering-token batch is 4/4 (100%). It uses the protected installed interpreter and guardian modules, with a synthetic expected-owner SID and the actual engineering account in the fixture server role. No synthetic account or token is acquired. These checks are not actual guardian-account or service lifecycle qualification. Both accounts remain disabled; no protected package, credential, policy, real journal/reference or broker state changed.

## Actual guardian-token check: verified

**Actual guardian verification is complete at 3/3 (100%).** Receipt `guardian-failure-paths-result-5c115cf7f5904616839357503a83e3ea.json` is independently accepted: all four cases pass with zero reference-handler calls, pipe closure and no residual impersonation token. Exact scenario/stdout pairs, empty error logs, three source hashes, retained literal bytes and administrator-owned protected child ACLs match. The 687 installed payload hashes and 792 ACL objects remain verified; both accounts are disabled. Earlier 67% preparation/retry instructions are superseded and need no repetition. It snapshots the diagnostic child into guardian Code with administrator ownership and exact protected file ACLs (owner/guardian ReadAndExecute, administrator/SYSTEM FullControl), binds its hash and checks its descriptor after execution, and runs four fresh hidden processes using the installed protected interpreter under AgenticGuardian. The local owner's SID is the configured owner; the child's process identity must match the actual guardian. The wrong-caller case uses a guardian child client connecting to the guardian's own pipe: native owner admission must reject that self-caller even though the pipe DACL grants its creator access.

Each process has an eight-second parent timeout. Client lifetime, transport connect/read deadlines and cleanup are bounded; successful cases require zero reference-handler calls, closed pipe, restored thread identity and no authority flags. The wrapper retains scenario diagnostics/source/receipt, disables the guardian in `finally` and re-audits the installed package. Host crash/forced wrapper termination can interrupt cleanup; inspect account state then. This is a disposable process/transport fixture, not a Windows service or deployed supervisor.

The following command is retained as historical procedure; this fixture is complete and needs no repetition:

```powershell
& 'C:\Users\cesar\OneDrive\AI\agentic-investing\scripts\test_webull_guardian_failure_paths.ps1'
```

Enter your **AgenticGuardian password** locally. Engineering cannot supply that owner-held credential. No runtime password is needed, and completed connection/DACL fixtures need no repetition. Share only the output/result path.

A pass establishes these bounded failures and guardian self-caller rejection under the actual guardian token. It does not qualify an unrelated local identity, remote-host denial, deployed owner-app/process isolation, Windows service lifecycle, real signed reference/journal integration or reset admission. Provider status/accounting/event contracts remain separate. Trial launch stays 0%, forward evidence 0/60; overall readiness remains unquantified.


Failure-source extraction repair: the formatter normalized the diagnostic Python literal to triple double quotes while the wrapper expected triple single quotes. The wrapper now uses the installed protected interpreter to parse Python AST and accept exactly one literal string assignment to CHILD, returning its UTF-8 bytes as base64 without importing/executing the driver. Six regression cases pass for both quote styles, literal extraction without top-level execution, nonliteral/duplicate/missing assignments; the current formatted driver extracts successfully through Windows PowerShell. The failure occurred before password/account enable. Both accounts are disabled; actual Guardian fixture remains prepared at 67%. Retry the same owner command; no installation or completed fixture repeat is required.


Restricted-environment startup repair: the retained partial-frame diagnostic shows FileNotFoundError/WinError 2 while launching the fixture client by the bare name powershell.exe. The wrapper intentionally supplies only System32 in PATH, so PowerShell's nested directory was unavailable. The diagnostic child now resolves the absolute Windows PowerShell executable beneath the supplied SystemRoot; the restricted environment, pipe permissions and deadlines are unchanged. All four installed-code checks pass under the reproduced small environment/System32-only PATH; eight targeted regression tests pass (client startup plus source extraction). Both accounts are disabled. Actual guardian-token fixture remains pending at 67%; retry the same command. No installed release or launch gate is promoted.
