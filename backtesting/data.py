"""Provider-neutral archives and materialized cutoff-only strategy views.

Adapters attest availability/vintage and calendar provenance. A view contains no
reference to the archive, so future rows are not accessible through strategy inputs.
"""

from datetime import datetime
from decimal import Decimal
from typing import Literal, Protocol

from pydantic import AwareDatetime, Field

from agents.long_term.models import FundamentalData, ResearchAssessment
from market_data.models import Symbol
from portfolio.state import Identifier, Nonnegative, Record
from portfolio.theses import PositionThesis
from technical.indicators import SessionBar, SessionHistory


class LookaheadViolation(ValueError):
    pass


class HistoricalBar(SessionBar):
    symbol: Symbol


class FundamentalObservation(Record):
    observation_id: Identifier
    available_at: AwareDatetime
    data: FundamentalData


class ResearchObservation(Record):
    observation_id: Identifier
    available_at: AwareDatetime
    assessment: ResearchAssessment
    thesis: PositionThesis


class HistoricalEvent(Record):
    event_id: Identifier
    symbol: Symbol
    occurred_at: AwareDatetime
    available_at: AwareDatetime
    text: str


class CorporateAction(Record):
    action_id: Identifier
    symbol: Symbol
    kind: Literal["split", "dividend", "symbol_change", "delisting", "merger"]
    effective_at: AwareDatetime
    available_at: AwareDatetime
    ratio: Decimal = Field(default=Decimal(1), gt=0, allow_inf_nan=False)
    cash_per_share: Nonnegative = Decimal(0)
    # v0.1 dividends must settle at the effective close; other schedules fail closed.
    payable_at: AwareDatetime | None = None


class UniverseObservation(Record):
    effective_at: AwareDatetime
    available_at: AwareDatetime
    symbols: tuple[Symbol, ...]


class HistoricalDataset(Record):
    dataset_id: Identifier
    version: Identifier
    source: Identifier
    calendar_id: Identifier
    sessions: tuple[AwareDatetime, ...]
    bars: tuple[HistoricalBar, ...]
    fundamentals: tuple[FundamentalObservation, ...] = ()
    research: tuple[ResearchObservation, ...] = ()
    events: tuple[HistoricalEvent, ...] = ()
    actions: tuple[CorporateAction, ...] = ()
    indicator_vintages: tuple[SessionHistory, ...] = ()
    universes: tuple[UniverseObservation, ...] = ()
    reliable: bool = False
    is_sample: bool = True
    corporate_actions_complete: bool = False
    point_in_time_universe_complete: bool = False


class HistoricalDataProvider(Protocol):
    def load(self, dataset_id: str, version: str) -> HistoricalDataset: ...


def check_known(value, cutoff):
    """Inspect nested typed timestamps, including source and amendment vintages.

    Planned future thesis review dates are scheduling metadata, not future facts.
    Opaque reference_data is not consumed and is rejected for historical research.
    """
    if hasattr(value, "model_dump"):
        value = value.model_dump(mode="python")
    if isinstance(value, datetime):
        if value > cutoff:
            raise LookaheadViolation("Nested evidence was not available at cutoff")
    elif isinstance(value, dict):
        for key, item in value.items():
            if key != "next_scheduled_review":
                check_known(item, cutoff)
    elif isinstance(value, (tuple, list)):
        for item in value:
            check_known(item, cutoff)


class PointInTimeView(Record):
    as_of: AwareDatetime
    bars: tuple[HistoricalBar, ...]
    fundamentals: tuple[FundamentalObservation, ...]
    research: tuple[ResearchObservation, ...]
    events: tuple[HistoricalEvent, ...]
    histories: tuple[SessionHistory, ...]
    universe: tuple[Symbol, ...]

    def history(self, symbol):
        return next((h for h in self.histories if h.symbol == symbol), None)


def snapshot(dataset, cutoff, fallback_universe=()):
    if cutoff.tzinfo is None:
        raise ValueError("Aware cutoff required")
    bars = tuple(b for b in dataset.bars if b.session_close <= cutoff and b.available_at <= cutoff)
    fundamentals = tuple(f for f in dataset.fundamentals if f.available_at <= cutoff)
    research = tuple(r for r in dataset.research if r.available_at <= cutoff)
    for item in (*fundamentals, *research):
        check_known(item, item.available_at)
        if isinstance(item, ResearchObservation) and item.assessment.reference_data:
            raise LookaheadViolation("Opaque historical reference data lacks availability contract")
    histories = []
    for symbol in sorted({h.symbol for h in dataset.indicator_vintages}):
        eligible = [
            h
            for h in dataset.indicator_vintages
            if h.symbol == symbol and h.adjustment_known_at <= cutoff
        ]
        if eligible:
            history = max(eligible, key=lambda h: h.adjustment_known_at)
            sessions = tuple(s for s in history.sessions if s <= cutoff)
            if sessions:
                histories.append(
                    SessionHistory.model_validate(
                        history.model_dump()
                        | {
                            "sessions": sessions,
                            "bars": tuple(
                                b
                                for b in history.bars
                                if b.session_close <= cutoff and b.available_at <= cutoff
                            ),
                        }
                    )
                )
    universes = [
        u for u in dataset.universes if u.available_at <= cutoff and u.effective_at <= cutoff
    ]
    universe = (
        max(universes, key=lambda u: (u.effective_at, u.available_at)).symbols
        if universes
        else fallback_universe
    )
    return PointInTimeView(
        as_of=cutoff,
        bars=bars,
        fundamentals=fundamentals,
        research=research,
        events=tuple(
            e for e in dataset.events if e.available_at <= cutoff and e.occurred_at <= cutoff
        ),
        histories=tuple(histories),
        universe=universe,
    )


def quality(dataset, config):
    findings = set()
    sessions = dataset.sessions
    if not sessions or tuple(sorted(set(sessions))) != sessions:
        findings.add("TIMESTAMP_INCONSISTENCIES")
    selected = tuple(s for s in sessions if config.start_date <= s.date() <= config.end_date)
    if selected and (
        selected[0].date() != config.start_date or selected[-1].date() != config.end_date
    ):
        findings.add("INTERVAL_ENDPOINT_NOT_SESSION")
    keys = [(b.symbol, b.session_close) for b in dataset.bars]
    if len(set(keys)) != len(keys):
        findings.add("DUPLICATE_OBSERVATIONS")
    if any(b.session_close not in sessions for b in dataset.bars):
        findings.add("TIMESTAMP_INCONSISTENCIES")
    for symbol in (*config.security_universe, config.benchmark):
        available = {
            b.session_close
            for b in dataset.bars
            if b.symbol == symbol and b.available_at == b.session_close
        }
        if not set(selected) <= available or not selected:
            findings.add(
                "INCOMPLETE_BENCHMARK_DATA" if symbol == config.benchmark else "MISSING_SESSIONS"
            )
    if any(
        (b.available_at - b.session_close).total_seconds() > config.max_observation_age_seconds
        for b in dataset.bars
    ):
        findings.add("STALE_OBSERVATIONS")
    if not dataset.corporate_actions_complete:
        findings.add("MISSING_CORPORATE_ACTIONS")
    if not dataset.fundamentals:
        findings.add("MISSING_FUNDAMENTALS")
    if not dataset.research:
        findings.add("MISSING_HISTORICAL_RESEARCH")
    for observations in (dataset.research, dataset.fundamentals):
        ids = [item.observation_id for item in observations]
        if len(ids) != len(set(ids)):
            findings.add("DUPLICATE_OBSERVATIONS")
    vintage_keys = [(h.symbol, h.adjustment_known_at) for h in dataset.indicator_vintages]
    if len(set(vintage_keys)) != len(vintage_keys):
        findings.add("DUPLICATE_OBSERVATIONS")
    if any(
        h.calendar_id != dataset.calendar_id or h.sessions != dataset.sessions
        for h in dataset.indicator_vintages
    ):
        findings.add("INDICATOR_CALENDAR_MISMATCH")
    if config.strategy.strategy_domain == "swing" and not dataset.indicator_vintages:
        findings.add("MISSING_INDICATOR_VINTAGES")
    if (
        config.universe_scope == "broad"
        and dataset.point_in_time_universe_complete
        and not all(
            any(u.effective_at <= s and u.available_at <= s for u in dataset.universes)
            for s in selected
        )
    ):
        findings.add("INCOMPLETE_POINT_IN_TIME_UNIVERSE")
    if not dataset.reliable:
        findings.add("UNRELIABLE_DATA")
    if dataset.is_sample:
        findings.add("SYNTHETIC_TEST_DATA")
    if len({a.action_id for a in dataset.actions}) != len(dataset.actions):
        findings.add("DUPLICATE_OBSERVATIONS")
    for action in dataset.actions:
        if action.kind not in {"split", "dividend"}:
            findings.add("UNSUPPORTED_CORPORATE_ACTION")
        if action.available_at > action.effective_at or action.effective_at not in sessions:
            findings.add("TIMESTAMP_INCONSISTENCIES")
        if action.kind == "dividend" and action.payable_at != action.effective_at:
            findings.add("UNSUPPORTED_DIVIDEND_SCHEDULE")
    return tuple(sorted(findings))
