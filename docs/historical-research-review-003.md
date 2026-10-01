# Historical data qualification v0.3 — SEC filing reconstruction

**Decision: SEC EDGAR is a conditional reconstruction source, but historical
strategy validation remains blocked.** The external FMP limitation is no
longer the primary blocker. SEC filing access worked, yet exact public
availability and original fact vintage are not proven. No development,
validation, or 2026 OOS strategy performance was calculated in this phase.

The new SEC adapter reconstructed 112 symbol-level 2023–2025 filings across
the ten fixed symbols; GOOG and GOOGL share one CIK, leaving 101 unique
accession records. All 112 had UTC acceptance timestamps, and 111 had at
least one strictly accession-matched USD XBRL metric. One TSLA amendment was
preserved separately and had no metric under the current strict tag map.
The knowledge boundary returned UNCERTAIN for all live reconstructed records
at 2025-12-31 because their original dissemination/value vintage could not be
verified. Earlier decisions return NOT_YET_KNOWN for later acceptances.

The existing `LONG_TERM_QUALITY_GROWTH v1.0.0` remains insufficient-data:
free cash flow, net-debt/EBITDA, FCF yield, valuation, thesis, portfolio fit,
and publication-safe reference data are not complete. No missing value was
inferred and no strategy parameter was optimized. `SWING_TREND_MOMENTUM
v1.0.0` was also untouched. Raw Alpaca prices remain separate from an
uncertified corporate-action vintage; this still blocks qualifying adjusted
strategy accounting and benchmark comparison.

The research-validation thresholds from review 002 remain frozen and were not
retested against unqualified data. The separate $160 whole-share feasibility
test was not rerun. The 2026 OOS dataset remained sealed; the staged runner
still refuses OOS release. The forward-paper counter remains **0/60**,
both strategies are **NOT_ELIGIBLE**, and paper/production execution remains
**DISABLED**. No BrokerAdapter order method was invoked.
The full repository suite passed 485 tests; Ruff passed. The sole test warning
is an existing Starlette/httpx TestClient deprecation warning.

See [SEC qualification](data-provider-qualification-sec-edgar.md),
[fundamental reconstruction](historical-fundamental-reconstruction.md), and
the existing [historical research runbook](historical-research-lab.md).
