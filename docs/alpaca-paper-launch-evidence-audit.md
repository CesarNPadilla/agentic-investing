# Remaining launch evidence audit

The historical 23/36 (64%) snapshot predates the ETF replacement and later runtime work. It remains an archive, not a refreshed launch percentage. The implemented ETF fixtures, authenticated read-only recovery, process watchdog, parent-crash containment and connection checkpoints are useful components; none substitutes for the missing source or authority contracts below.

| Gate | Current evidence | Required next step |
| --- | --- | --- |
| Initial security status | Alpaca authentication/subscription verified; initial status UNKNOWN | Provider-supported bootstrap and applicable halt coverage |
| Complete activity publication | Bounded pagination and immutable replay implemented | Authoritative publication boundary/delay and correction contract |
| Account/activity as-of coherence | Cash/quantity equality observed; acquisition/snapshot cutoff gap retained | Provider-supported coherence contract, followed by implementation/tests |
| Opening cash journal | Executed USD JNLC recognized; baseline-day effective time ambiguous | Owner/provider record establishing inclusion or effective timestamp |
| Protected risk-reset authority | Real passkey proof and scoped read-only recovery verified | Independent Windows identity/permissions boundary and qualified action/counter lifecycle |
| Persistent service | Bounded process/event monitoring and parent-crash child containment tested | Service installation, ongoing operation/reporting and crash/session recovery qualification |
| Disconnect event coverage | Fresh checks before event dispatch; interrupted records block | Source gap/replay contract and qualified gap reconciliation |
| Real paper order runtime | ETF roundtrip/reservations/restart fixtures; mutations mock-only | Admission integration and real paper order qualification after source/authority gates pass |

The [provider questions](alpaca-paper-provider-evidence-questions.md) make the external evidence request concrete. The owner can obtain those answers through authenticated support. No policy exception is inferred from a request to continue. The selected Alpaca-only, ETF-only, INTC-disabled, Nasdaq-deferred and UNKNOWN-blocks-orders rules remain.

The account activity documentation describes a nontrade activity date as occurrence or settlement date and gives a date-only sample. It does not establish that the separately observed journal `created_at` equals the economic effective time. Pagination instructions describe traversing available records; they do not establish a publication watermark. The stock status documentation describes status events but does not establish a full initial snapshot guarantee in the reviewed page. These are findings about the reviewed [activity](https://docs.alpaca.markets/us/docs/account-activities) and [status](https://docs.alpaca.markets/us/docs/real-time-stock-pricing-data) documentation, not inferred provider guarantees.

Daily P&L remains unevaluated while whole-day external flows are unqualified. Quiet streams and zero returned activities remain insufficient evidence. All risk latches stay intact; paper/production orders, trial startup, forward-session counting and live permission remain disabled. This audit changes documentation/evidence only, so no code-test rerun is required.
