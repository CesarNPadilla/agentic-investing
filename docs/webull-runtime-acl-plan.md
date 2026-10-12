# Windows paper-runtime access plan

`AgenticPaperRuntime` is now present, disabled, a member of Users only, and not a member of Administrators. Direct group inspection found no additional memberships. This verifies provisioning, not effective process-token privileges or access isolation. No account was enabled and no runtime task or service was launched.

The next deployment layout is a new administrator-owned `C:\ProgramData\AgenticInvestingPaper` tree, separate from the writable development checkout and existing credential folders. Existing folders must not be adopted or recursively changed without reviewing their contents and ACLs. Avoid granting the runtime access to the owner's whole profile or OneDrive workspace.

| Proposed area | Runtime identity | Protected owner/controller boundary |
| --- | --- | --- |
| Immutable runtime code/config | Read/execute | Install/update through controlled provisioning |
| Runtime logs and proposal outbox | Modify | Read; treat proposals as untrusted |
| Authoritative risk state/reset counters | No direct access | Validate, persist and enforce |
| Broker secrets with trading authority | No access | Broker calls only after admission |
| Owner credential and signed approvals | No access | Action-bound verification and replay protection |
| Published diagnostic receipts | Read only | Write verified results |

Runtime-writable requests never become authoritative approvals. Published receipts cannot permit bypassing the protected controller. The protected execution boundary must own actual broker order calls and fail closed if the controller or risk state is unavailable. An account name and directory ACLs alone do not implement this boundary.

Next engineering step: prepare an exclusive new-directory provisioning script and a read-only ACL audit, then have the owner apply the reviewed script with administrator privileges. Do not copy existing broker credentials, passkey enrollment or risk ledgers into runtime-readable folders. Qualification must test read/write/ACL-change/reset and credential access attempts under the real runtime token, using disposable fixtures. Enabling the account and service logon remain later explicit deployment steps; provisioning does not authorize trading.

The [directory provisioning script](../scripts/prepare_paper_runtime_directories.ps1) is now prepared. It refuses an existing root or an enabled/unexpectedly grouped runtime account, requires a distinct explicitly named owner, applies protected administrator-owned ACLs to each new empty directory, and compares the applied ACL with the planned rules. No existing path is recursively changed, and no credential or code is copied. Failure can leave a partial empty tree; retain it for inspection rather than rerunning or deleting blindly. Root enumeration is allowed, but protected RiskState/BrokerSecrets/OwnerControl children have no runtime grant; real-token access checks remain required. Runtime Modify access to Logs/Outbox is not authority to reset risk state.

Run directly in elevated 64-bit PowerShell, naming the current owner's Windows login explicitly:

```powershell
& 'C:\Users\cesar\OneDrive\AI\agentic-investing\scripts\prepare_paper_runtime_directories.ps1' -OwnerAccount "$env:COMPUTERNAME\cesar"
```

The engineering process is not elevated and has not executed provisioning. Syntax and an isolated disposable directory ACL roundtrip can be checked without provisioning the deployment tree. The resulting owner/controller grant is a filesystem boundary only; protected controller implementation and runtime-token verification remain pending.

Provisioning verification: after the owner's “done”, all nine directory ACLs (root plus eight children) matched the planned explicit SID/right/inheritance rules. Every directory has inheritance disabled and administrator ownership; all eight child directories are empty. The runtime account remains disabled. [Actual verification evidence](examples/webull-sandbox/runtime-acl-verification.json) supersedes the earlier preparation-only observation. Do not rerun directory creation. This is an ACL configuration audit, not a process-token access test or a qualified controller.

The next identity-dependent check requires a real process running as AgenticPaperRuntime. Because the account is disabled and its password is owner-held, this cannot be performed from the current session. Prepare an owner-run bounded fixture test that prompts for credentials locally, temporarily enables the account only for that test, always disables it afterward, and verifies code/config immutability, allowed log/outbox writes, and denied protected-state/credential access. That test must use dummy fixtures and no broker credentials or network calls. No such enablement or test has occurred yet.

The [bounded access-test script](../scripts/test_paper_runtime_access.ps1) is prepared; parent and embedded child syntax are validated. Run it directly in elevated 64-bit PowerShell. It prompts for the runtime password locally, creates uniquely named dummy fixtures, starts a hidden standard-user process for at most 30 seconds, and disables the account in a nested finally block even if process termination fails. It checks actual identity, administrator status, six protected/read-only areas and two allowed-write areas, then verifies protected fixture contents and probe code hash from the owner process. A host crash or forced termination of the owner wrapper can interrupt cleanup; inspect/disable the account directly if that happens. No password enters chat or source code. Retained fixture results do not qualify ACL-change denial, full token privileges, controller authentication, or live broker isolation.

Actual access-test follow-up: the wrapper reported a blank process exit code, but the retained runtime report contained all eight passing file-access checks, the expected identity and non-admin status. Independent owner-context inspection confirmed every protected dummy file remained unchanged, the retained child script exactly matched the reviewed embedded probe, and the account was disabled again. [Verified evidence](examples/webull-sandbox/runtime-access-verification.json) accepts the scoped file-access checks while explicitly retaining process exit-code verification as false. No rerun is needed to establish these retained permission observations.

The wrapper now retains the child process handle before waiting, drains redirected output after exit, and distinguishes an unavailable exit code from a nonzero exit. A current-identity process smoke passed; the revised alternate-credential wrapper itself has not been rerun. ACL-change denial, controller/reset admission and full credential/broker isolation remain pending. Trading stays disabled.

The owner-run access script now adds six dummy-file DACL-write attempts, using the existing owner-provided descriptors and applying only the Access section. It never modifies deployment-directory permissions or grants new access. The parent verifies unchanged fixture contents, code, descriptor inputs and DACLs, and requires the new report schema plus denied DACL writes. This is prepared, not run under the runtime identity. It tests fixture WRITE_DAC denial, not every directory escalation or controller admission path. Run the same command directly in elevated 64-bit PowerShell and enter the AgenticPaperRuntime password chosen during account creation; do not share it. The bounded wrapper temporarily enables that identity and disables it in cleanup. No broker credentials or network calls are involved.

Owner-run follow-up: the retained v2 report records all six protected-file access/DACL checks passing and both writable-area checks passing. Independent inspection confirmed unchanged protected fixture contents and DACLs, exact agreement between retained child code and reviewed source, and a disabled runtime account. [New scoped evidence](examples/webull-sandbox/runtime-access-dacl-verification.json) supersedes the earlier prepared-only status for these checks. The owner reports that the wrapper completed successfully; its numerical process exit code was not separately persisted for independent inspection. Directory-level ACL escalation and protected controller/reset/broker isolation remain unqualified. No repeat of the completed dummy-file test is needed.
