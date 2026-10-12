# Durable daily-loss observer diagnostics

The read-only observer now invokes the account-bound paper daily-loss diagnostic.
Missing New York calendar-midnight equity evidence blocks evaluation. Retained
boundary source claims are immutable and carry a source digest and description;
retention does not qualify the source. Intraday request/receipt timestamps cannot
substitute for broker equity as of midnight. No baseline was created for the
actual account by this change.

The diagnostic uses 1% of fixed start-of-day equity, subtracts reconciled external
flows from daily equity change, and treats equality with the loss threshold as
a breach. Missing flow reconciliation or an old/unstable snapshot prevents a
P&L result. A breach is latched in durable state; subsequent equity recovery or
restart cannot release it. There is no automatic liquidation or reset authority.

The current observer supplies no qualified flow total and always preserves the
boundary-source qualification blocker. Tests use explicitly labelled local
fixtures. This implements persistence and observer wiring but does not establish
an actual trusted daily baseline or authenticated reset procedure.

Readiness remains 22/36 (61%). Daily baseline source qualification, authenticated
resets, clock-policy approval, trading-status/stream health, coherent account and
ledger cutoffs, supervised event/timer monitoring, and real paper broker acceptance
remain launch blockers. No order submission or month trial was started.
