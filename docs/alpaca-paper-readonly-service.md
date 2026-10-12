# Windowed read-only service preparation

The empty-account diagnostic service can run successive bounded, process-supervised observation windows during the published NYSE regular session. It preserves all risk latches and refuses active exposure, failed or abandoned service records, and invalid diagnostic receipts. A private stop marker ends observation between windows. A missing calendar session or insufficient time before close ends the run without opening another window.

This is diagnostic infrastructure. Each connection has its own reconciliation checkpoint; gaps between windows remain unqualified. It does not implement an order runner, continuous fill coverage, automatic failure recovery, or a protected owner risk-reset authority.

The Windows task `AgenticInvesting-PaperReadOnlyObserver` is installed **disabled**, with no triggers, current-user interactive limited privileges, no automatic retries, overlapping instances ignored, and a 24-hour execution limit. It uses the fixed windowless Python entry point and references private inputs outside the repository. Its exported XML and diagnostic log remain private. Task registration did not start background observation. The current Windows principal is an operating-system execution identity, not proof of the declared owner's identity or reset authorization.

The initial dedicated-account smoke run completed two five-second windows with four completed source checks per window. Execution and trial-start flags remained false. The unchanged blockers include unknown initial market status, activity publication completeness, baseline-day funding ambiguity, snapshot cutoff coherence, settled cash, independent reset authority, and an unqualified order runtime. See [the provider evidence questions](alpaca-paper-provider-evidence-questions.md).

Validation: 312 selected tests pass, including failed/abandoned service refusal, source-free stop/session-close behavior, active-exposure rejection and activation-flag rejection. Source digests and deployment observations are in [the evidence record](examples/alpaca-paper-month/readonly-service-preparation.json). Current ETF scope remains SCHB only; INTC stays disabled. No month trial or live trading has started, and historical readiness percentages are unchanged.

Windows task settings follow [Microsoft's task settings documentation](https://learn.microsoft.com/en-us/powershell/module/scheduledtasks/new-scheduledtasksettingsset?view=windowsserver2025-ps).
