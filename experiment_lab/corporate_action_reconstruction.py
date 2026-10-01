"""Provider-neutral corporate-action evidence and deterministic research accounting.

No output from this module authorizes strategy validation or broker execution.
"""

import hashlib
import json
from dataclasses import dataclass
from datetime import UTC, date, datetime
from decimal import Decimal
from enum import StrEnum

from experiment_lab.historical_records import RawHistoricalPriceBar

ENGINE_VERSION = "historical-adjustment-v0.5"
CUTOFF = date(2025, 12, 31)
SECURITIES = {
    "AAPL": "US0378331005", "MSFT": "US5949181045", "NVDA": "US67066G1040",
    "AMZN": "US0231351067", "GOOGL": "US02079K3059", "GOOG": "US02079K1079",
    "META": "US30303M1027", "TSLA": "US88160R1014", "PLTR": "US69608A1088",
    "INTC": "US4581401001", "VOO": "US9229083632",
}


class KnowledgeState(StrEnum):
    EVENT_KNOWN_AT_T = "EVENT_KNOWN_AT_T"
    EVENT_NOT_YET_KNOWN_AT_T = "EVENT_NOT_YET_KNOWN_AT_T"
    EVENT_AVAILABILITY_UNCERTAIN = "EVENT_AVAILABILITY_UNCERTAIN"


class EconomicState(StrEnum):
    EVENT_ECONOMICALLY_EFFECTIVE = "EVENT_ECONOMICALLY_EFFECTIVE"
    EVENT_NOT_YET_EFFECTIVE = "EVENT_NOT_YET_EFFECTIVE"
    EVENT_TERMS_UNVERIFIED = "EVENT_TERMS_UNVERIFIED"


@dataclass(frozen=True)
class LedgerEvent:
    security_id: str
    source_symbol: str
    event_type: str  # FORWARD_SPLIT, REVERSE_SPLIT, REGULAR_DIVIDEND, SPECIAL_DIVIDEND
    provider: str
    source_event_id: str | None
    declaration_date: date | None
    publication_at: datetime | None
    publication_proven: bool
    ex_date: date
    record_date: date | None
    payment_date: date | None
    effective_date: date
    amount: Decimal | None
    ratio: Decimal | None  # new shares per old share
    currency: str | None
    retrieved_at: datetime
    raw_source_reference: str
    source_digest: str
    event_version: int = 1
    supersedes: str | None = None
    data_quality: str = "UNVERIFIED"
    terms_verified: bool = False

    def __post_init__(self):
        if self.source_symbol not in SECURITIES or self.security_id != SECURITIES[self.source_symbol]:
            raise ValueError("Unpinned or mismatched security identity")
        if self.ex_date > CUTOFF or self.effective_date > CUTOFF:
            raise ValueError("Reserved 2026 OOS event")
        if self.retrieved_at.tzinfo is None or (self.publication_at is not None
                                               and self.publication_at.tzinfo is None):
            raise ValueError("Event instants require timezones")
        if self.publication_proven and self.publication_at is None:
            raise ValueError("Publication proof requires a timestamp")
        if self.event_version < 1 or not self.source_digest or not self.raw_source_reference:
            raise ValueError("Event provenance incomplete")
        split = self.event_type in {"FORWARD_SPLIT", "REVERSE_SPLIT"}
        dividend = self.event_type in {"REGULAR_DIVIDEND", "SPECIAL_DIVIDEND"}
        if not split and not dividend:
            raise ValueError("Unsupported event type")
        if split and (self.ratio is None or self.ratio <= 0 or self.amount is not None
                      or (self.event_type == "FORWARD_SPLIT" and self.ratio <= 1)
                      or (self.event_type == "REVERSE_SPLIT" and self.ratio >= 1)):
            raise ValueError("Invalid split terms")
        if dividend and (self.amount is None or self.amount <= 0 or self.ratio is not None
                         or self.currency != "USD" or self.payment_date is None
                         or self.payment_date < self.ex_date):
            raise ValueError("Invalid cash distribution terms")

    @property
    def event_key(self) -> str:
        return f"{self.provider}:{self.source_event_id or self.source_digest}:v{self.event_version}"


@dataclass(frozen=True)
class SourceTermEvidence:
    security_id: str
    event_type: str
    source: str
    source_digest: str
    source_reference: str
    ex_date: date | None = None
    payment_date: date | None = None
    amount: Decimal | None = None
    ratio: Decimal | None = None
    publication_at: datetime | None = None
    publication_proven: bool = False


def compare_source_terms(event: LedgerEvent, evidence: SourceTermEvidence) -> dict:
    if (event.security_id != evidence.security_id or event.event_type != evidence.event_type):
        return {"status": "IDENTITY_MISMATCH", "matched": [], "missing": [],
                "conflicts": ["security_or_type"]}
    matched, missing, conflicts = [], [], []
    fields = (("ex_date", "ratio") if "SPLIT" in event.event_type
              else ("ex_date", "payment_date", "amount"))
    for field in fields:
        observed = getattr(evidence, field)
        expected = getattr(event, field)
        if expected is None:
            continue
        if observed is None:
            missing.append(field)
        elif observed != expected:
            conflicts.append(field)
        else:
            matched.append(field)
    status = ("CONFLICT" if conflicts else "PARTIAL" if missing else "TERMS_MATCH")
    return {"status": status, "matched": matched, "missing": missing,
            "conflicts": conflicts, "publication_proven": evidence.publication_proven}


def normalize_alpaca_event(kind: str, row: dict, retrieved_at: datetime) -> LedgerEvent:
    """Current feed terms are retrospective; its dates do not prove publication."""
    symbol = row["symbol"]
    mapping = {"forward_splits": "FORWARD_SPLIT", "reverse_splits": "REVERSE_SPLIT",
               "cash_dividends": ("SPECIAL_DIVIDEND" if row.get("special")
                                  else "REGULAR_DIVIDEND")}
    if kind not in mapping:
        raise ValueError("Unsupported Alpaca action type")
    event_type = mapping[kind]
    day = lambda key: date.fromisoformat(row[key]) if row.get(key) else None
    ratio = None
    if "SPLIT" in event_type:
        ratio = Decimal(str(row["new_rate"])) / Decimal(str(row["old_rate"]))
    raw = json.dumps(row, sort_keys=True, separators=(",", ":"), default=str).encode()
    ex = day("ex_date")
    return LedgerEvent(
        security_id=SECURITIES[symbol], source_symbol=symbol, event_type=event_type,
        provider="Alpaca", source_event_id=row.get("id"),
        declaration_date=day("declaration_date"), publication_at=None,
        publication_proven=False, ex_date=ex, record_date=day("record_date"),
        payment_date=day("payable_date"), effective_date=ex,
        amount=(Decimal(str(row["rate"])) if "DIVIDEND" in event_type else None),
        ratio=ratio, currency=("USD" if "DIVIDEND" in event_type else None),
        retrieved_at=retrieved_at, raw_source_reference=f"Alpaca:{kind}:{row.get('id')}",
        source_digest=hashlib.sha256(raw).hexdigest(), data_quality="SOURCE_ONLY",
    )


def knowledge_state(event: LedgerEvent, at: datetime) -> KnowledgeState:
    if at.tzinfo is None:
        raise ValueError("Decision time must be timezone-aware")
    if not event.publication_proven or event.publication_at is None:
        return KnowledgeState.EVENT_AVAILABILITY_UNCERTAIN
    return (KnowledgeState.EVENT_KNOWN_AT_T if event.publication_at <= at
            else KnowledgeState.EVENT_NOT_YET_KNOWN_AT_T)


def economic_state(event: LedgerEvent, at: date) -> EconomicState:
    if not event.terms_verified:
        return EconomicState.EVENT_TERMS_UNVERIFIED
    return (EconomicState.EVENT_ECONOMICALLY_EFFECTIVE if event.effective_date <= at
            else EconomicState.EVENT_NOT_YET_EFFECTIVE)


class CorporateActionRepository:
    def __init__(self):
        self._versions: dict[str, LedgerEvent] = {}

    def add(self, event: LedgerEvent) -> None:
        key = event.event_key
        if key in self._versions:
            if self._versions[key] != event:
                raise ValueError("Conflicting duplicate corporate-action version")
            return
        if event.supersedes and event.supersedes not in self._versions:
            raise ValueError("Correction references unknown version")
        if event.supersedes:
            prior = self._versions[event.supersedes]
            if (prior.security_id != event.security_id or prior.event_type != event.event_type
                    or event.event_version <= prior.event_version):
                raise ValueError("Invalid correction lineage")
        self._versions[key] = event

    def current(self) -> tuple[LedgerEvent, ...]:
        superseded = {event.supersedes for event in self._versions.values() if event.supersedes}
        return tuple(sorted((event for key, event in self._versions.items()
                             if key not in superseded), key=lambda e: (e.ex_date, e.event_key)))

    def all_versions(self) -> tuple[LedgerEvent, ...]:
        return tuple(self._versions.values())


def reconcile(primary: tuple[LedgerEvent, ...], secondary: tuple[LedgerEvent, ...]) -> dict:
    """Explicit mismatches; a missing secondary row is not proof of no event."""
    matched, missing, conflicts = [], [], []
    for event in primary:
        candidates = [other for other in secondary if other.security_id == event.security_id
                      and other.event_type == event.event_type and other.ex_date == event.ex_date]
        if not candidates:
            missing.append(event.event_key)
        elif len(candidates) != 1 or (event.amount, event.ratio, event.payment_date) != (
                candidates[0].amount, candidates[0].ratio, candidates[0].payment_date):
            conflicts.append(event.event_key)
        else:
            matched.append(event.event_key)
    return {"matched": matched, "missing_secondary": missing, "conflicts": conflicts}


def qualify_gates(*, provenance: bool, terms: bool, splits_complete: bool,
                  distributions_complete: bool, availability: bool, effective_dates: bool,
                  versions: bool, reproducible: bool, raw_immutable: bool,
                  independent_reconciliation: bool, benchmark_consistent: bool,
                  no_lookahead: bool, oos_sealed: bool) -> dict:
    checks = locals()
    gates = {name: ("PASS" if value else "FAIL") for name, value in checks.items()}
    gates["historical_accounting"] = ("PASS" if all(checks[name] for name in (
        "provenance", "terms", "splits_complete", "distributions_complete",
        "effective_dates", "versions", "reproducible", "raw_immutable",
        "independent_reconciliation", "benchmark_consistent", "no_lookahead", "oos_sealed"))
        else "FAIL")
    gates["historical_research_signal"] = (
        "PASS" if gates["historical_accounting"] == "PASS" and availability else "FAIL")
    return gates


def adjusted_bars(bars: tuple[RawHistoricalPriceBar, ...],
                  events: tuple[LedgerEvent, ...], *, coverage_complete: bool) -> dict:
    if not coverage_complete or any(not e.terms_verified for e in events):
        return {"status": "INSUFFICIENT_DATA", "reason": "UNVERIFIED_EVENT_COVERAGE_OR_TERMS"}
    if not bars or len({b.symbol for b in bars}) != 1 or any(b.adjustment_mode != "raw" for b in bars):
        raise ValueError("One immutable raw symbol series required")
    symbol = bars[0].symbol
    if any(e.source_symbol != symbol for e in events):
        raise ValueError("Action/security mismatch")
    if len({e.event_key for e in events}) != len(events):
        raise ValueError("Duplicate corporate-action event")
    dates = [b.timestamp.astimezone(UTC).date() for b in bars]
    if dates != sorted(set(dates)) or dates[-1] > CUTOFF:
        raise ValueError("Unordered, duplicate, or OOS bars")
    splits = [e for e in events if "SPLIT" in e.event_type]
    output = []
    for bar, day in zip(bars, dates, strict=True):
        factor = Decimal(1)
        used = []
        for event in splits:
            if event.effective_date > day:
                factor *= event.ratio
                used.append(event.event_key)
        output.append({"date": day.isoformat(), "open": str(bar.open / factor),
                       "high": str(bar.high / factor), "low": str(bar.low / factor),
                       "close": str(bar.close / factor), "volume": str(bar.volume * factor),
                       "factor": str(factor), "raw_digest": bar.source_digest,
                       "event_ids": sorted(used), "engine_version": ENGINE_VERSION})
    return {"status": "EXPLORATORY_RESEARCH", "series": output,
            "qualifying_validation": False}


def account_returns(bars: tuple[RawHistoricalPriceBar, ...],
                    events: tuple[LedgerEvent, ...], *, coverage_complete: bool,
                    initial_shares: Decimal = Decimal(1), reinvest: bool = False,
                    sessions: tuple[date, ...] | None = None) -> dict:
    """Ex-date entitlement, payment-date cash, optional close-price reinvestment."""
    adjusted = adjusted_bars(bars, events, coverage_complete=coverage_complete)
    if adjusted["status"] == "INSUFFICIENT_DATA":
        return adjusted
    dates = tuple(bar.timestamp.astimezone(UTC).date() for bar in bars)
    if sessions is not None and dates != sessions:
        return {"status": "INSUFFICIENT_DATA", "reason": "MISSING_OR_MISALIGNED_SESSIONS"}
    if any(e.effective_date == dates[0] for e in events):
        return {"status": "INSUFFICIENT_DATA", "reason": "OPENING_POSITION_BASIS_UNVERIFIED"}
    if any("SPLIT" in split.event_type and "DIVIDEND" in dividend.event_type
           and split.effective_date == dividend.ex_date
           for split in events for dividend in events):
        return {"status": "INSUFFICIENT_DATA", "reason": "SAME_DAY_SPLIT_DIVIDEND_BASIS_UNVERIFIED"}
    if initial_shares <= 0:
        raise ValueError("Initial shares must be positive")
    for event in events:
        if ("DIVIDEND" in event.event_type and event.ex_date in dates
                and event.payment_date <= dates[-1] and event.payment_date not in dates):
            return {"status": "INSUFFICIENT_DATA", "reason": "MISSING_PAYMENT_SESSION"}
    shares, cash, receivable = initial_shares, Decimal(0), Decimal(0)
    entitlements: dict[str, Decimal] = {}
    initial_value = bars[0].close * initial_shares
    price_basis_shares = initial_shares
    rows = []
    for bar, day in zip(bars, dates, strict=True):
        used = []
        for event in events:
            if "SPLIT" in event.event_type and event.effective_date == day:
                shares *= event.ratio
                price_basis_shares *= event.ratio
                used.append(event.event_key)
        for event in events:
            if "DIVIDEND" in event.event_type and event.ex_date == day:
                entitlements[event.event_key] = shares * event.amount
                receivable += entitlements[event.event_key]
                used.append(event.event_key)
            if "DIVIDEND" in event.event_type and event.payment_date == day:
                # Entitlement is locked at ex-date, including intervening share changes.
                payment = entitlements.pop(event.event_key, None)
                if payment is None:
                    return {"status": "INSUFFICIENT_DATA", "reason": "DIVIDEND_ENTITLEMENT_MISSING"}
                cash += payment
                receivable -= payment
                used.append(event.event_key)
        if reinvest and cash:
            shares += cash / bar.close
            cash = Decimal(0)
        rows.append({"date": day.isoformat(), "shares": str(shares), "cash": str(cash),
                     "dividend_receivable": str(receivable),
                     "price_value": str(price_basis_shares * bar.close),
                     "total_value": str(shares * bar.close + cash + receivable),
                     "event_ids": sorted(set(used)), "engine_version": ENGINE_VERSION})
    return {"status": "EXPLORATORY_RESEARCH", "qualifying_validation": False,
            "methodology": ("TOTAL_RETURN_REINVESTED" if reinvest
                            else "TOTAL_RETURN_CASH_DIVIDENDS"),
            "price_return": str(Decimal(rows[-1]["price_value"]) / initial_value - 1),
            "total_return": str(Decimal(rows[-1]["total_value"]) / initial_value - 1),
            "series": rows}
