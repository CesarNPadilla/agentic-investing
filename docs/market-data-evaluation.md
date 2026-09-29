# Phase 1: external market-data integration

Status: evaluation in progress; provider selection and live verification pending.

## Current integration boundary

`MarketDataProvider.get_quote` already returns a validated quote with source,
timezone-aware observation time, currency, decimal price, and sample marker.
The API accepts injected providers, but settings and default construction currently
support only the synthetic provider. Docker explicitly sets that provider.

## Shortlist

Reviewed official documentation on 2026-09-29. Entitlements depend on the selected
account and plan; verify them before enabling external calls.

| Candidate | Fit for this lab | Evaluation concern |
| --- | --- | --- |
| Twelve Data | Standalone market-data service with quote and time-series endpoints | Confirm symbol coverage, credit budget, allowed personal use, and adjustment semantics for the chosen plan |
| Alpha Vantage | Quote and historical-data endpoints for a small research prototype | Confirm daily quota and which adjusted-history endpoints require premium access |
| Alpaca Market Data | US equity market-data API | Free live IEX coverage is a single exchange; preserve feed identity and avoid interpreting it as consolidated market coverage |

Sources:
- https://twelvedata.com/docs
- https://twelvedata.com/pricing
- https://www.alphavantage.co/documentation/
- https://www.alphavantage.co/support/
- https://docs.alpaca.markets/us/docs/market-data-faq

## Adapter acceptance criteria

1. Explicit provider configuration and credentials outside OneDrive; retain sample
   as the default. Fail clearly when a selected provider lacks credentials.
2. Preserve actual observation time, feed/source, currency, and price meaning.
   Do not substitute retrieval time or silently label a daily close as a live quote.
3. Bound connection/read timeouts and retries. Honor rate limits; do not retry
   authentication failures or unsupported symbols. Never log API keys.
4. Map unknown symbols to `SymbolNotFound`, and transport, entitlement, quota, or
   invalid provider responses to `ProviderUnavailable`. Never fall back silently
   from real data to sample data.
5. Use offline response fixtures to test timestamp conversion, decimal precision,
   missing/null fields, symbol mismatch, throttling, authentication, and timeouts.
6. For historical bars, record timezone/session, feed, and split/dividend adjustment
   policy; validate pagination, ordering, duplicates, and completeness before
   computing indicators.
7. Verify one entitled symbol end to end against PostgreSQL after local credential
   setup, without placing credentials or raw personal data in the repository.

## Pending choice

Select a provider based on any existing subscription, intended symbols, acceptable
delay, and budget. No subscription has been purchased, external adapter enabled,
or live market-data call made during this evaluation.
