# Webull cash activity observation retention

The selected cash sandbox account now has a private SQLite diagnostic store outside the repository. A fresh read-only acquisition revalidated the selection before and after fetching activities, retained one empty page observation, and verified its stored payload digest. No credentials, account identifiers or raw activity records are copied into public evidence.

`portfolio/webull_activity_store.py` binds the store to the private selected-account digest. Initialization refuses existing files; appends use transactions and unique observation identifiers. Separate acquisitions remain separate observations, including identical or empty results. Restart verification checks the account binding and payload digests before accepting another append. Local receipt time records persistence, not a broker snapshot or economic effective time.

The module exposes no update/delete operation, but this is not an immutable ledger: someone with file write access could alter the database and its digests or delete observations. There is no independent anchor, deletion detection, protected runtime deployment or reset authority. Windows protection and controller integration remain separate qualification work.

The store accepts only diagnostic evidence with execution/trial disabled, an unknown external-flow total and the unresolved publication, effective-time and account-as-of blockers. It does not classify flows, deduplicate provider records, establish publication completeness, construct a midnight baseline or apply accounting. An empty returned page remains an observation, never proof of zero flows.

Validation covers independent empty observations across restart, initialization/duplicate refusal, rollback, promotion rejection, account mismatch and damaged payload detection. The accompanying [qualification record](examples/webull-sandbox/activity-observation-store-qualification.json) records the actual observation and exact source digests. Trading remains disabled; the month trial has not started.
