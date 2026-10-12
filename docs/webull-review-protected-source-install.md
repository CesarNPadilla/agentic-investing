# Webull review: protected source installation

The next owner-dependent step installs only the six pinned review source files. The current engineering process is not elevated. The installer therefore requires direct elevated PowerShell; it does not attempt automatic elevation. No password entry, owner signing, broker call, account enablement, interpreter installation or service/task creation is part of this step.

Prepared bundle:

`C:\Users\cesar\AppData\Local\AgenticInvesting\staging\webull-review-source-7383c8e053d7445cb470112f30455dc1`

Manifest SHA256:

`3f83d3a65cead1c1aa1ca0d9446df741694fc520470ed6b65d140f9eb5e0ad43`

The bundle contains the signature verifier, review journal, frozen-consumption checkpoint, separate review app and its HTML/JavaScript. Its explicit manifest disallows execution authority. Python and PowerShell validation check the externally supplied manifest digest, exact source inventory and every file digest; extra files, altered sources, foreign scope and path substitutions are rejected. The staging folder is a development copy, not a protected deployment.

Run this exact command in **elevated 64-bit PowerShell**, under the same owner Windows account used for the earlier provisioning:

```powershell
& 'C:\Users\cesar\OneDrive\AI\agentic-investing\scripts\install_webull_review_source.ps1' `
  -SourceBundle 'C:\Users\cesar\AppData\Local\AgenticInvesting\staging\webull-review-source-7383c8e053d7445cb470112f30455dc1' `
  -ExpectedManifestSha256 '3f83d3a65cead1c1aa1ca0d9446df741694fc520470ed6b65d140f9eb5e0ad43'
```

The new target is `C:\ProgramData\AgenticInvestingPaper\OwnerControl\WebullReviewSource-3f83d3a65cead1c1`. The script requires the existing protected administrator-owned OwnerControl parent, only owner/Administrators/SYSTEM authorities, and a disabled runtime account. It refuses an existing target and any reparse point encountered in the checked parent/bundle paths. Every newly copied item receives protected administrator ownership and an exact read-back ACL: Administrators/SYSTEM FullControl, owner ReadAndExecute, no runtime grant. Source hashes are checked again after copying. Existing parent permissions and existing fixtures are not changed.

If the command succeeds, share its output. Engineering will independently inspect installed hashes, ownership/ACLs and disabled runtime status before accepting the source-installation step. On failure, retain the partial directory and share the error; do not delete it or rerun blindly. The protected source-installation batch is 3/4 prepared/verified steps (75%); actual installation plus inspection is the remaining step.

This is a source boundary, not a qualified controller. The Python interpreter/dependencies, package search path, actual process/token isolation, private state, lifecycle supervision and real Windows Hello ceremony remain unqualified. The trusted owner can replace children through the existing parent's authority, and an administrator can change protection; these ACLs do not establish an independent recovery anchor or prevent a jointly privileged rollback. No real owner envelope, approval journal or credential copy is created.

The staged [frozen review checkpoint](../security/webull_review_checkpoint.py) requires one cryptographically verified consumed review and a separate reference directory. Seven tests cover restart verification, consumption deletion, unconsumed state, absent/changed references and scope/authority tampering. It never advances a checkpoint or authorizes recovery. Deletion or rollback is detected only against a surviving trusted reference; jointly replacing that reference is outside its guarantee. It is not wired into a trading or reset path.

Webull status/accounting/event answers remain independently required through the [prepared provider request](webull-provider-evidence-questions.md). Source installation can proceed while those answers are pending. Trial launch remains 0%, forward evidence 0/60, and overall Webull readiness remains unquantified.

## Installation verified

The owner reported successful installation. A separate read-only audit verified the installed manifest and all six source hashes, the exact protected administrator-owned ACLs on all nine objects, absence of runtime grants/reparse points in the inspected release and a disabled AgenticPaperRuntime account. The source-installation batch is now 4/4 (100%). [Retained verification](examples/webull-sandbox/review-protected-source-verification.json) supersedes the earlier 75% preparation status. Do not rerun the installer or replace the installed release.

The next preparation audit inventoried the current Python interpreter and five directly used libraries through an isolated, no-bytecode subprocess. The interpreter still resolves its base installation under the owner's profile and its dependencies from the writable development checkout. `-I -B` controls environment/user-site/cwd lookup and bytecode writes; it does not make those interpreter or library files protected. This inventory therefore does not qualify an execution environment or start the app. Interpreter/dependency deployment, complete import/native-library search paths, private state/recovery and actual owner signing remain engineering dependencies.
