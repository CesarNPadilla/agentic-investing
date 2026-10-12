# Exact midnight source and bounded status monitor

The Alpaca paper account's continuous, one-minute portfolio history returns an
exact America/New_York midnight equity point. The new read-only adapter requests
the completed midnight interval, requires ordered unique integer timestamps,
equal-length equity arrays, an exact midnight entry, finite positive equity,
and unchanged account binding across authenticated account reads. Redirects and
provider failures block. No nearest timestamp or previous close is substituted.

The exact source record was retained in the private account-bound ledger without
printing equity or account identity. The reader preserves its response digest.
Retained records cannot be silently replaced if the provider revises them.
The paper observer evaluates the fixed 1% daily threshold using that record.
External-flow reconciliation is still missing, so daily P&L remains unavailable.
No acceptance credit is claimed for an incomplete daily-loss runtime gate.

The observer now checks daily loss before acquiring quotes, so quote failure
cannot skip loss evaluation. It returns sanitized component-specific failure
codes and preserves the completed daily diagnostic. Actual quote reads returned
a future event timestamp and were rejected; the original strict quote-time rule
was preserved. Clock qualification alone does not make every quote admissible.

A real authenticated INTC status subscription was monitored for 20 seconds with
bounded transport pings. It completed with no status events; the status remains
UNKNOWN. Quiet-stream absence never establishes trading eligibility. This is a
bounded read-only probe, not the month runner or a continuously supervised service.

The owner has been asked whether to add Nasdaq's official trading-halt source
for qualification alongside Alpaca. Source selection and freshness/completeness
qualification remain separate. An empty or missing feed cannot clear a gate.
No alternate status source is activated pending that answer.

References: [Alpaca portfolio history](https://docs.alpaca.markets/us/reference/getaccountportfoliohistory-1)
documents continuous overnight valuation and timestamps; [Alpaca market-data FAQ](https://docs.alpaca.markets/us/docs/market-data-faq)
points to Nasdaq's official halt information; [Nasdaq feed announcement](https://www.nasdaqtrader.com/TraderNews.aspx?id=ETA2010-76)
describes the halt/pause feed's exchange coverage.

Readiness remains 23/36 (64%). Baseline-source integration is progress but does
not complete flow reconciliation or authenticated resets. Runtime execution,
actual paper broker acceptance, and the month trial remain blocked. No orders
were sent and no human reset or source approval was invented.
