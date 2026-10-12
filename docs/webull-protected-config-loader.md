# Protected guardian configuration loader

Native engineering checks are complete: 12 Windows cases cover exact protected reads, changed ACL/write grants, changed ownership, unprotected DACLs, hard links, oversize, noncanonical/alternate-stream paths, wrong process identity, held-file write denial and symbolic-link rejection. With configuration and release regressions, 39 tests pass. Ruff passes.

The reader opens the guardian root, Code parent and configuration with native non-inheritable handles and read-only sharing. It inspects security descriptors and attributes through those same handles before and after reading bounded bytes. Objects must be administrator-owned with protected exact four-role ACLs: administrators/SYSTEM FullControl, configured owner/guardian ReadAndExecute. Reparse points, extra rules and multi-link files are rejected. The credentialed loader checks actual guardian process identity before opening configuration, validates the externally supplied digest/release/context and rejects role mismatch. It constructs no host and grants no reset or execution authority.

This checks the guardian root and Code anchor, not a newly qualified whole-volume/ProgramData boundary. Administrators, prior writable mappings, complete rollback, system compromise and power-loss behavior are outside the guarantee. Caller role/hash expectations must come from trusted deployment. Native filesystem calls need an external process deadline; the owner fixture applies a bounded outer wait. A synchronized production clock and exact journal/reference directory qualification remain required before admission. [Microsoft file security guidance](https://learn.microsoft.com/en-us/windows/win32/fileio/file-security-and-access-rights) describes handle security inspection; [CreateFile documentation](https://learn.microsoft.com/en-us/windows/win32/api/fileapi/nf-fileapi-createfilea) describes read sharing and reparse-point handling.

The separate version-four package is installed at `C:\ProgramData\AgenticInvestingGuardian\Code\GuardianRelease-c46afdaf67cb70f4`. Manifest SHA-256: `c46afdaf67cb70f437507f5975791c5fb461a3cfdf1774a72b4c9ae573774c41`. All 694 payload hashes and 800 exact protected objects are audited. An installed-interpreter engineering protected read/parse passed; its role inputs were taken from the disposable fixture for this engineering smoke only, not asserted as independent production provisioning evidence. Earlier releases remain retained.

| Scoped step | Progress |
| --- | --- |
| Native loader engineering checks | 100% |
| Protected package install/audit | 100% |
| Actual guardian fixture preparation | 100% |
| Actual guardian protected configuration read | 0% |

## Next local action

Run in elevated 64-bit owner PowerShell:

```powershell
& 'C:\Users\cesar\OneDrive\AI\agentic-investing\scripts\test_webull_guardian_config_loader.ps1'
```

Enter the existing AgenticGuardian password locally. The script makes fresh protected synthetic configuration/public-credential material, then checks the installed loader under the actual guardian token. It retains receipts and diagnostics and disables the account again. The five-minute synthetic review context must still be current when the password is entered; expiration blocks the check and retains evidence. Each invocation creates new files; no existing review state is deleted or repaired.

This fixture creates no real signing credential, journal/reference directories or running host. It does not exercise an owner passkey ceremony, signed-host/service operation, reset or trading. Earlier supervision and reply fixtures are complete and need no repetition. Both accounts are disabled at this checkpoint. Trial launch stays 0%, forward evidence 0/60 and overall readiness unquantified. Webull technical contracts, actual protected provisioning, signed-host/service lifecycle and atomic reset admission remain unresolved.


Actual guardian protected-loader verification accepted: fixture c586a8342cea4d8e880914d4430aec31 is independently verified. Configuration/probe/receipt/wrapper hashes, two exact administrator-owned protected file ACLs, configured actual role bindings, empty stderr/expected stdout and receipt time inside the synthetic envelope window match. All 694 installed hashes and 800 protected objects remain audited; both accounts are disabled. This scoped actual guardian read is now 100%; prior 0% password instructions are historical and no repeat is needed. The fixture loaded synthetic public material only. Actual journal/reference directory provisioning, signed-host/app operation, service lifecycle, owner passkey signing, Webull technical contracts and atomic reset admission remain unresolved. No service, real signature/reference/journal, reset, order or trial was activated. Trial launch remains 0%, forward evidence 0/60 and overall readiness unquantified.
