# Durable paper fill accounting

Added an isolated durable fill ledger initialized from a verified stable, unblocked, empty $1,000 paper observation. The actual dedicated account passed initialization and a bounded real activity import returned zero activities. Private ledger state lives at `C:/Users/cesar/AppData/Local/AgenticInvesting/alpaca-paper-fill-ledger-v1.sqlite`. Existing account/state files were preserved. This opening observation is not a New York midnight daily-loss baseline.

Activities retain immutable canonical payload digests by ID and account binding. Exact overlapping replays have no additional cash/share effect. Changed activity payloads, acquisition gaps/regression, incomplete pagination, order identity changes, missing cumulative fills and unexplained borrowing/shorts reject the transaction. Trade cash and positions rebuild from the immutable opening baseline inside the same SQLite transaction as accepted activity IDs and cutoff advancement. Tests cover restart, atomic rollback after a correction, concurrent replay and unknown activities. A failed import blocks the caller; it does not clear any latch or create release permission.

Unknown non-FILL activity is retained and latches for review without changing cash. Fees, flows and settlement are deliberately unresolved rather than treated as zero. Execution stays unavailable, existing reservations remain staged/unsubmitted, and no buying power is interpreted as settled cash. The one-day acquisition overlap is a bounded recovery aid, not a guarantee against arbitrarily delayed publication; broader historical rescan/correction policy remains needed. No broker/account mutation, order submission or synthetic evidence relabeling occurred. Actual fill handling is fixture-tested; no real fill was generated merely to exercise the implementation.

The CLI refuses repository-local state and can re-import safely without --initialize:

```powershell
.\.venv\Scripts\python.exe -m scripts.reconcile_alpaca_paper_fills --env-file 'C:\Users\cesar\AppData\Local\AgenticInvesting\alpaca-paper-trial.env' --ledger-file 'C:\Users\cesar\AppData\Local\AgenticInvesting\alpaca-paper-fill-ledger-v1.sqlite'
```

Validation: **100 targeted tests passed**, including 6 new durable-ledger tests. Ruff checks, [status JSON](examples/alpaca-paper-month/durable-fill-ledger-status.json), source digests and git diff --check pass.

Next: qualify/map fee and external-flow activity plus settlement evidence, bind ledger differences to account reconciliation, integrate durable loss monitoring, independent clock/status and external reset, then implement paper-only order lifecycle and persistent scheduling. The trial remains unstarted, forward paper 0/60, 2026 OOS sealed and live execution disabled.
