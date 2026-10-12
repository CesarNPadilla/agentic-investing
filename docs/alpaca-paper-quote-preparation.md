# Alpaca paper preparation - bid/ask evidence

The read-only `AlpacaPaperQuoteReader` now collects explicit IEX best bid/ask through the [official latest-quotes endpoint](https://docs.alpaca.markets/us/reference/stocklatestquotes-1). It records aware provider event time, local receipt time, USD currency, source and exact response SHA-256. The existing research last-trade adapter and all execution flags remain unchanged. This separate observation model does not relabel real data as synthetic risk evidence.

Crossed/nonpositive/nonfinite quotes, unexpected symbols, missing fields, naive/future timestamps, HTTP/auth/quota failures and redirects fail closed. No automatic retry, source fallback or live broker operation exists. The original quote-age bound is 30 seconds inclusive; a future receipt relative to evaluation also blocks. Trading status remains UNKNOWN and an unverified-status reason is always emitted. Receipt timestamps do not prove synchronized clocks. Consumers must evaluate freshness again at decision time.

An authenticated read-only AAPL IEX smoke check passed. It returned QUOTE_TIME and QUOTE_STATUS_UNVERIFIED, so it did not qualify for an order. Stale off-session data is retained as an observation rather than treated as fresh. AAPL here is a connectivity probe, not a selected strategy security. No account data, credentials or raw responses were written to the repository.

Validation: 39 quote/preflight/readiness tests passed; new status JSON parses and source digests match; git diff --check passes. [Status artifact](examples/alpaca-paper-month/quote-preparation-status.json) records the limited result.

Next: qualified trading-status/clock and NYSE calendar evidence, complete paper-account reconciliation, durable reservations/loss/reset control integration and persistent paper-only scheduling. Strategy/version/symbols remain unselected under the owner's preparation-first instruction. The month clock has not begun; qualifying sessions remain 0/60. Paper and live order submission remain disabled; this phase changes no strategy, historical/OOS evidence or executable policy.
