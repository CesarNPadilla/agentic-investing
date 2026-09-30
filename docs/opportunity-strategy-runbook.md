# Opportunity & Strategy Engine v0.1 runbook

Trusted internal Python workflow only; no HTTP route or scheduled job is installed.
Research -> Thesis -> Opportunity -> Strategy -> TradeProposal -> Risk -> Human Review.
Execution is outside the implemented boundary; execution_available is always false.

## Local workflow

1. Load persisted ResearchAssessment and resulting current PositionThesis. The thesis must
   retain the assessment review ID, timestamp and direction. News is not a direct input.
2. Supply coherent opening/current PortfolioState, reviewed experimental attribution,
   kill-switch state and approved InvestmentPolicy. Keep active private data outside sync.
3. Supply StrategyVersion: unique ID/version, domain, creation time, authorization_reference,
   EntryConfig and optional SwingConfig. Configure research freshness, evidence requirements,
   reviewed valuation/fit and sizing for this context. Decisions start UNSET; changing
   configuration requires a new version. This phase selects no production parameters.
4. Initialize StrategyStore on a local research SQLAlchemy engine. This is additive bootstrap,
   not an approved production migration. Run with explicit time and reliable fee estimate:

```python
from strategies.service import OpportunityStrategyService
from strategies.storage import StrategyStore

store = StrategyStore(engine)
store.initialize()
result = OpportunityStrategyService(store).run(
    assessment, thesis, opening_state, current_state, policy,
    strategy_version, kill_switch, now=evaluation_time,
    fees=estimated_fees, history=session_history, validation=strategy_validation,
)
opportunity = store.opportunity(result["opportunity"]["opportunity_id"])
```

Variables refer to validated local records. history and validation may be None for long-term.
For an executable synthetic example see test_persisted_full_workflow_stops_at_human_review
in tests/test_opportunity_strategy.py. Tests explicitly opt into synthetic evidence.

## Models and outcomes

InvestmentOpportunity retains scope/symbol/timestamps, classification(s), domain, assessment
digest and thesis links, portfolio/security roles, allocation, supporting/opposing evidence,
catalysts, risks, valuation, fit, concentration, horizon, quality, missing data, uncertainty
and policy findings. IDENTIFIED is not purchase permission. Legacy/nonallowlisted holdings
remain analyzable; a rejected purchase never liquidates them. GOOG/GOOGL keep exact security
identity: a canonical GOOGL assessment cannot silently authorize a GOOG purchase.

LongTermStrategy.evaluate requires complete fresh research, active noninvalidated thesis,
purchase permission, reviewed valuation/fit, concentration evaluation, rationale, risks and
invalidation conditions. Price changes affect sizing, not thesis status. Weak/invalidated
theses, concentration flags and sourced material-event categories trigger EXIT_REVIEW:
fundamental_deterioration, competitive_deterioration, management_failure, valuation_dislocation,
better_capital_allocation, catalyst_completed, structural_industry_change.

SwingStrategy requires SWING_ELIGIBLE thesis metadata and reviewed research parameters.
Entry is fast SMA above slow SMA; size is bounded by risk budget / ATR stop distance,
configured maximum notional and experimental capital. Parameters include SMA periods,
ATR stop/profit multiples, maximum sessions and separate calendar-day limit. review_exit
deterministically checks stop, target, trend reversal and holding period, yielding review
data only. These close-based rules make no intrabar fill assumption. Existing policy swing
controls and 60-session forward validation still apply; test parameters do not qualify them.

TradeProposal preserves existing schema names:

| Concept | Stored representation |
| --- | --- |
| symbol / side / quantity | trade.symbol / trade.side / trade.quantity |
| limit / notional | trade.limit_price / quantity times price |
| entry logic | proposed_entry and trade.entry_thesis |
| created_at | timestamp |
| invalidation / evidence | invalidation_condition / supporting_data_references |
| strategy/version/opportunity/assessment | strategy_id, strategy_version, strategy_domain, strategy_configuration_digest, opportunity_id, research_assessment_id |
| concentration / funding | concentration_before, concentration_after, experimental_capital_required |
| horizon, thesis, rationale, catalysts, risks, exit, impact | existing named fields |
| data time / lifecycle | data_timestamp / status |

The proposal remains an immutable RISK_REVIEW snapshot; bundle.review holds REJECT,
INSUFFICIENT_DATA or REQUIRE_HUMAN_REVIEW. Individual risk checks are retained. No approval
is granted by changing a label; this phase never assigns APPROVED_FOR_PAPER and has no live
approval state. No proposal contains an execution method.

Legacy research-proposal digests remain verifiable only when every new metadata field has
its default value. Adding opportunity metadata cannot reuse a legacy digest. Existing
freshness, policy and thesis checks still apply; compatibility grants no authorization.

Concentration before/after uses target-symbol market value / whole-portfolio equity;
after includes pending symbol buys and subtracts fees from equity. Cash-funded buys do not
increase equity. Existing policy risk separately retains largest-symbol/gross-exposure limits.

Experimental accounting reuses experimental_utilization: attributed acquisition cost,
reserved commitments, availability, realized/unrealized P/L and strategy attribution are
stored. Unknown P/L stays null. Existing holdings consume no experimental capital unless
explicitly attributed. Whole-share sizing is bounded; independent risk enforces USD 160,
cash, open orders, losses, concentration, long-only, no margin/leverage and required controls.
Research proposals do not reserve capital or change a ledger. Percentage sizing remains
an extension point through PositionSizer; fixed notional and ATR-bounded budgets are implemented.

## Indicators and historical use

TechnicalIndicatorService.calculate takes SessionHistory and an aware as_of. Supply exact
ordered exchange close instants covering the history, including holidays and early closes.
Missing completed sessions block calculations. Bars not available at the cutoff are excluded.
Fully adjusted OHLCV and adjustment_known_at <= as_of are required. Historical runs require
the vintage known then, not a retrospectively adjusted latest download.

Calculations: SMA, SMA-seeded EMA, Wilder RSI/ATR, sample volatility of simple returns
annualized by configurable annual_sessions (research default 252), relative strength as ratio
of cumulative gross returns minus one, average volume, period return and peak-to-trough
drawdown. Decimal arithmetic is deterministic; flat RSI is 50. Missing optional benchmark
leaves relative_strength null with a named gap; core indicators remain usable. A supplied
misaligned/unreliable benchmark makes the snapshot insufficient.

Historical/current/paper-research inputs use the same evaluate method. Material decisions
replay identically; per-evaluation IDs vary. Future harnesses must retain code revision,
dataset vintage, survivorship controls and fill/cost assumptions as well as these snapshots.

## Storage and audit

Tables: opportunity_strategy_versions_v1 and opportunity_evaluations_v1. Identical version
registration is idempotent; changed definitions conflict. Concurrent first registration may
hit the unique constraint; reload and compare before retrying. Evaluation bundles commit
opportunity, result, proposal/review, inputs and correlated timestamped events atomically.
Persistence failure propagates: callers must not publish a result before persistence succeeds.
Version registration can remain after a failed evaluation. No job lease or scheduler exists.

Readers: get(opportunity_id), opportunity(id), version(id, version), history(scope, symbol,
limit=100). History is bounded at 500 and ID-ordered, not chronological. Authenticate and
authorize scopes before future API exposure; never expose private input bundles in logs.

## Remaining gates and verification

Owner decisions: experimental baseline/attribution, daily/experimental losses, risk freshness
and timezone, valuation/fit and sizing/concentration decisions, strategy authorization and
all swing parameters/stricter policy controls. Research defaults cannot fill risk controls.

Data: verified SEC/IR/news/reference provenance, reliable fees/marks, coherent full broker
ledger, ETF look-through, aligned benchmarks, licensed OHLCV, exchange calendars and historical
adjustment vintages. No new live provider is wired. Calendar/provenance flags remain adapter
attestations. PostgreSQL migrations/concurrency/restore, API scopes and qualification remain open.

Use the Python environment in docs/verification.md. Run full pytest, repository Ruff lint,
and format checks on strategies, technical/indicators.py, risk/proposals.py, risk/workflow.py
and tests/test_opportunity_strategy.py. No credentials or broker calls are needed.
