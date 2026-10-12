# Guardian runtime rejection: verified fixture

**Verification is complete at 3/3 (100%).** Owner receipt `guardian-runtime-denial-result-e9dff439-7ba5-4873-9257-2a98640b1dd1.json` is independently accepted: actual runtime Win32 5/no payload, standard-owner success on the same pipe, nested receipts, five source/receipt hash links, exact retained child, matching gate/readiness and four empty diagnostics. All 687 installed payload hashes and 792 exact protected ACL objects still pass. The prior 67% preparation status is superseded; no fixture rerun is needed. Both accounts stay disabled. The installed guardian package is unchanged. This is an owner-run diagnostic, not service deployment or reset authority.

The runtime child is compiled and waiting before the guardian starts, keeping compiler startup outside the guardian's five-second connect/read deadline. Once the guardian publishes its local pipe name, the owner writes a gate in runtime-read-only Receipts. The actual AgenticPaperRuntime child verifies its SID/non-admin role, checks read access to its Logs directory, then attempts the same pipe access mask used by the owner client. Only Win32 `ACCESS_DENIED` (5) counts as denial; missing pipe, timeout and other errors fail. No runtime payload is sent. After that denial, the standard-owner client must send the exact synthetic frame to the same live guardian pipe and produce the existing guardian receipt. This positive control distinguishes an owner-only DACL from an absent or dead server.

The wrapper uses small replacement environments and no loaded user profiles. It retains child code, readiness, gate, diagnostics and receipts; binds child/wrapper/helper/receipt hashes in a final owner summary; checks empty diagnostics and unchanged guardian release; and disables both accounts in `finally`. Host crash or forced wrapper termination can interrupt cleanup; inspect account state then. Partial fixtures are retained, never deleted or automatically reused.

Preparation checks passed: wrapper and embedded child parsing, both native helper compilations, successful read-control smoke, and a missing pipe returning Win32 2 rather than an accepted denial. A disposable administrator-only pipe separately denied an actual same-owner standard token with Win32 5, then accepted the elevated token and exact dummy frame on the same pipe. These checks are not the actual runtime-to-guardian qualification and do not establish deployed service privileges or adversarial process isolation.

The following owner command is retained as historical procedure; it is complete and needs no repetition:

```powershell
& 'C:\Users\cesar\OneDrive\AI\agentic-investing\scripts\test_webull_guardian_runtime_denial.ps1'
```

Enter **AgenticGuardian**, then **AgenticPaperRuntime**, passwords locally when prompted. Use the passwords chosen for those Windows accounts, not broker passwords or a Windows Hello PIN. Do not share either password. Engineering cannot launch those actual identities without direct local credential entry. Share only the output/result path.

A pass qualifies the actual runtime pipe-DACL denial plus the synthetic standard-owner control. Other identity rejection, remote-host denial, deployed owner-app/process isolation, service lifecycle, real signed reference/journal integration and reset admission remain separate. The script makes no broker calls and grants no execution authority. Trial launch stays 0%, forward evidence 0/60; overall readiness is unquantified. Provider status/accounting/event contracts remain unresolved.
