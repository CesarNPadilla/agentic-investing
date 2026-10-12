# Dedicated Windows paper-runtime identity

Exact owner decision: “a dedicated non-admin Windows runtime account”. The proposed account is `AgenticPaperRuntime`. Read-only host checks found it absent and the engineering process not elevated. No account, group, permission or credential change was attempted.

The [owner provisioning script](../scripts/prepare_paper_runtime_account.ps1) creates that account **disabled**, prompts locally for a SecureString password, refuses an existing account, and verifies Users-only group membership. It does not request elevation, store a password, grant a service logon, enable the account, register a task, copy secrets or change ACLs. A provisioning failure after account creation leaves an incomplete disabled account for review; rerunning will refuse to overwrite it. These checks do not qualify full effective privileges or access isolation.

The owner must run this script directly in elevated 64-bit PowerShell:

```powershell
& 'C:\Users\cesar\OneDrive\AI\agentic-investing\scripts\prepare_paper_runtime_account.ps1'
```

Next deployment design keeps runtime code and configuration read-only to that account. Mutable runtime logs are separate from protected policy, risk latch/reset counters, owner passkey receipts and approval records. Runtime-writable state cannot be the authoritative source of latch clearing. Broker credentials with order authority must stay with the protected execution/controller boundary, not the untrusted proposal runtime. The existing SDK and credential files have not been granted to the new identity.

The controller must validate action-bound human approvals, freshness, counter/replay protections, and approved next-NYSE-day reset ordering. No loopback HTTP origin, username declaration or passkey test alone proves OS caller authorization. ACLs, process identity, direct reset attempts, code/config tampering and credential access must be tested under the actual runtime token before acceptance. The current interactive engineering session remains under the owner identity; merely preparing a second account does not isolate this session.

No ACL migration is performed on OneDrive or the existing private directories. Deployment requires a separate protected location and a reviewed ACL matrix, with protected controller code and policy outside runtime write authority. Administrator access is a trusted provisioning boundary, not protection against local administrators.

Sources: [Microsoft New-LocalUser](https://learn.microsoft.com/en-us/powershell/module/microsoft.powershell.localaccounts/new-localuser?view=powershell-5.1) documents disabled creation and SecureString passwords; [icacls](https://learn.microsoft.com/en-us/windows-server/administration/windows-commands/icacls) documents Windows ACL management. Account provisioning is the next owner/admin action. Trading, trial startup and reset authority remain disabled and unqualified.

Provisioning follow-up: the owner's “done” was checked against Windows. `AgenticPaperRuntime` exists and is disabled, Users membership is present, Administrators membership is absent, and no other local-group membership was found. [Verification evidence](examples/webull-sandbox/runtime-account-verification.json) records the actual observation time rather than inventing an approval timestamp. Account provisioning is satisfied; [directory/controller isolation](webull-runtime-acl-plan.md) remains pending. Do not rerun the account-creation script.
