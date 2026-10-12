# Dedicated review guardian provisioning

The owner explicitly chose “Dedicated non-admin guardian account.” This selects an independent reference-writer boundary. It does not activate a service, reset, broker or trial. Engineering selected the routine local account name `AgenticGuardian` (15 characters) and a 35-character description, within Windows account/description limits.

Run the prepared command directly in **elevated 64-bit PowerShell** under the same owner Windows identity:

```powershell
& 'C:\Users\cesar\OneDrive\AI\agentic-investing\scripts\prepare_webull_guardian.ps1'
```

It prompts locally for a unique guardian password as a SecureString. Choose and retain it yourself; do not share it in chat. Although the engineering process has administrator access, this owner-held password is the required human-only provisioning input. The script does not store the password in source, logs or a service configuration, and disposes its local SecureString.

The script refuses an existing account or target, verifies a disabled paper runtime and the ProgramData parent boundary, creates the guardian **disabled** with Users-only membership, and provisions a new empty administrator-owned protected root: `C:\ProgramData\AgenticInvestingGuardian`. It leaves existing runtime/controller trees unchanged and grants no direct tree access to AgenticPaperRuntime.

| New area | Owner review identity | Guardian identity | Administrators/SYSTEM |
| --- | --- | --- | --- |
| Root, Code, Config | ReadAndExecute | ReadAndExecute | FullControl |
| References, Receipts, Logs | ReadAndExecute | Modify | FullControl |

Protected inheritance and exact ACL readback apply to all six directories. The new root is outside owner-writable OwnerControl. Parent checks reject standard-identity child-deletion grants on ProgramData that would undermine the root boundary. Administrators retain trusted provisioning authority; an elevated owner can therefore modify this tree. The online owner review app must eventually run with a qualified standard token, rather than the current elevated provisioning token.

Guardian Modify is a trusted-writer grant, not immutable/append-only filesystem protection against a compromised guardian. The guardian protocol must enforce exclusive write-ahead references, authenticate callers and verify original action-bound signatures; it cannot become reset authority. Files created later need separately checked ownership/ACLs, and account-token privileges, transport, process isolation and actual owner-reference deletion denial remain unqualified until tested. No guardian service logon rights, service, task, interpreter, credentials, real reference or risk state is installed in this step.

Script parsing and a disposable native Windows ACL roundtrip passed for the root plus five child directories. The fixture used the existing disabled runtime SID only as a substitute principal on temporary directories; it did not assign guardian authority to that account or enable it. These checks verify applied configuration, not actual guardian-token isolation. The guardian provisioning batch is 2/3 (67%): owner choice recorded, script/ACL preparation verified, owner creation plus independent inspection pending.

Share the command's success output for independent account/group/ACL inspection. On failure retain the partial disabled account/tree for review; do not delete it or rerun blindly. No repeated source/environment installer or paper-runtime password test is required. Trial launch stays 0%, forward evidence 0/60 and trading remains disabled.

## Provisioning verified

The owner's successful command output was independently checked against Windows. AgenticGuardian exists, is disabled, belongs only to Users and is distinct from the owner and paper runtime. All six administrator-owned protected directory ACLs match the planned four-principal grants exactly; the five child directories are empty, and the root contains only those children. AgenticPaperRuntime is disabled. [Retained verification](examples/webull-sandbox/guardian-provisioning-verification.json) advances this batch to 3/3 (100%). Earlier preparation/password instructions are historical; do not repeat account creation.

This accepts account and directory provisioning only. Actual guardian/standard-owner token access, protected guardian code, authenticated transport, service lifecycle and independent reference operations remain unqualified. No guardian service or real reference is deployed by these checks.
