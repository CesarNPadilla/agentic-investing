# Historical research provider and experiment registry

| Input | Adapter | Current qualification | Research use |
| --- | --- | --- | --- |
| Raw daily OHLCV | `AlpacaRawPriceProvider` | CONDITIONAL: immutable retrieval snapshot, IEX feed only | Development/validation price diagnostics; requires calendar and action handling |
| Calendar close | `AlpacaTradingCalendarProvider` | CONDITIONAL: exchange closes supplied, including early closes | Map daily date labels to trading sessions |
| Corporate actions | `AlpacaCorporateActionProvider` | FAIL for historical knowledge; creation time not guaranteed | Separately retained, excluded from qualifying decisions until vintage proven |
| Financial statements | `FmpHistoricalFundamentalProvider` | FAIL: HTTP 402 and revisions unproven | No strategy input |

The provider-neutral contracts live in `experiment_lab/provider_contracts.py`.
No provider adapter may submit an order. Read-only retrieval credentials come
from external files and are never part of provenance or artifacts.

| Experiment | Scope | State |
| --- | --- | --- |
| `historical-plan-001` | 2023–2024 development, 2025 validation, reserved 2026 OOS | Prior adjusted-price counterfactual diagnostic, validation failed; OOS unopened |
| `historical-qualification-audit-002` | New raw-price snapshot through 2025-12-31 and FMP qualification | Frozen gates recorded; qualifying validation NOT_RUN; OOS unopened |

The local registry, original plan, immutable raw snapshot, and audit are under
`C:\Users\cesar\AppData\Local\AgenticInvesting`. Their paths and digests are
evidence references, not production configuration. The original current-vintage
2022–2026 adjusted export is nonqualifying and must not be used to open the
2026 holdout. See [review 002](historical-research-review-002.md).
