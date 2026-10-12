# Synthetic review layout qualification

The preparation script supports only explicit synthetic qualification. It loads pinned configuration through the installed protected reader, validates the release/roles/current synthetic context, rejects existing paths and reparse ancestry, then creates fresh separate directories and an empty journal. Existing contexts and partial evidence are never reused or removed. All three new objects are administrator-owned with exact protected ACLs. Guardian has Modify on the reference directory and ReadAndExecute on the owner journal; the owner has the reciprocal roles. Administrators/SYSTEM retain FullControl. Runtime has no direct grant.

A disposable layout was created and independently inspected. A same-owner non-admin process obtained a journal write handle without writing, verified the empty journal, and was denied reference-file creation. Its token identity/non-elevation, retained probe/receipt hashes and unchanged journal bytes are verified. This does not establish actual owner signature consumption or full parent-directory/rollback resistance. The journal remains owner-writable and can be replaced by that owner; retained guardian evidence is intended to reject mismatches. Full guardian compromise and deletion/restoration of all state remain outside this design's guarantee.

| Scoped step | Progress |
| --- | --- |
| Synthetic layout provisioning and exact ACL checks | 100% |
| Actual standard-owner access check | 100% |
| Guardian access fixture preparation | 100% |
| Actual guardian journal/reference access | 0% |

## Next local action

Run in elevated 64-bit owner PowerShell:

```powershell
& 'C:\Users\cesar\OneDrive\AI\agentic-investing\scripts\test_webull_guardian_layout_access.ps1'
```

Enter the existing AgenticGuardian password locally. Each invocation prepares a fresh synthetic configuration and layout, then the actual guardian reads the empty journal, must be denied a journal write open, and writes a retained synthetic reference marker. The wrapper verifies unchanged journal bytes, marker path/scope, receipts and diagnostics, then disables the account. A five-minute context expiry fails closed if credential entry takes too long. Preparation mode was executed without prompting or enabling accounts; the final wrapper syntax was checked.

The marker is an access fixture, not a signed review intent or recovery reference. No owner signing credential is enrolled and no review host, service, reset or broker is activated. Both accounts remain disabled. Earlier configuration/supervision checks need no repetition. Actual signed-host/app operation, service lifecycle, independent provisioning history, real owner passkey ceremony, Webull status/accounting/event evidence and atomic reset admission remain pending. Trial launch stays 0%, forward evidence 0/60 and overall readiness unquantified.


Actual guardian synthetic layout access accepted: receipt c28a02f0aaf8413c893a871cc11d73e6 independently verifies the configured guardian identity, empty-journal read, denied journal write open and retained synthetic marker write. Eight retained hash links, five exact protected-object ACLs, marker ownership/scope, actual role bindings, clean diagnostics and disabled accounts match. The configuration was current at the fixture time; the owner journal remains byte-identical and contains no consumed review, intent or confirmation. The 694-file/800-object package remains audited. Actual guardian layout access is 100% for this synthetic fixture; earlier 0% password instructions are historical and no repeat is needed. Signed owner consumption, actual signed-host/app operation, service lifecycle, independent provisioning history, real owner passkey ceremony, provider contracts and atomic reset admission remain pending. No host/service, real approval/reference, reset, broker order or trial was activated. Trial launch remains 0%, forward evidence 0/60 and overall readiness unquantified.
