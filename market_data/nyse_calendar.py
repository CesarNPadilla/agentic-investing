"""Bounded published NYSE equity schedule; never infers halt or broker status."""
import hashlib
from datetime import date, datetime, time, timedelta
from pathlib import Path
from typing import Literal
from zoneinfo import ZoneInfo

from pydantic import BaseModel, ConfigDict, Field, model_validator

NY = ZoneInfo("America/New_York")


class PublishedCalendar(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    schema_version: Literal["nyse-equity-calendar-v1"]
    version: str = Field(min_length=1)
    source_url: Literal["https://www.nyse.com/trade/hours-calendars"]
    source_review_date: date
    coverage_start: date
    coverage_end: date
    timezone: Literal["America/New_York"]
    regular_open: Literal["09:30"]
    regular_close: Literal["16:00"]
    holidays: tuple[date, ...]
    early_closes: dict[date, Literal["13:00"]]
    extraordinary_closures_verified: Literal[False]

    @model_validator(mode="after")
    def valid_dates(self):
        if self.coverage_start > self.coverage_end or len(set(self.holidays)) != len(self.holidays):
            raise ValueError("Invalid coverage or duplicate holidays")
        for day in (*self.holidays, *self.early_closes):
            if not self.coverage_start <= day <= self.coverage_end or day.weekday() >= 5:
                raise ValueError("Invalid closure date")
        if set(self.holidays) & set(self.early_closes):
            raise ValueError("Conflicting closures")
        return self


class ScheduledSession(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    day: date
    opens_at: datetime
    closes_at: datetime
    calendar_version: str
    calendar_sha256: str
    execution_available: Literal[False] = False


class CalendarCoverageError(ValueError):
    pass


class NysePublishedCalendar:
    def __init__(self, path: Path):
        raw = path.read_bytes()
        self._calendar = PublishedCalendar.model_validate_json(raw)
        self.digest = hashlib.sha256(raw).hexdigest()

    def session(self, day: date):
        c = self._calendar
        if not c.coverage_start <= day <= c.coverage_end:
            raise CalendarCoverageError("Date outside reviewed NYSE coverage")
        if day.weekday() >= 5 or day in c.holidays:
            return None
        close = time.fromisoformat(c.early_closes.get(day, c.regular_close))
        return ScheduledSession(day=day, opens_at=datetime.combine(day, time(9,30), NY),
            closes_at=datetime.combine(day, close, NY), calendar_version=c.version,
            calendar_sha256=self.digest)

    def next_trading_day(self, day: date):
        self.session(day)  # Reject unknown starting-day coverage too.
        candidate = day + timedelta(days=1)
        while self.session(candidate) is None:
            candidate += timedelta(days=1)
        return candidate

    def schedule_reasons(self, now: datetime):
        if now.tzinfo is None or now.utcoffset() is None:
            raise ValueError("Aware evaluation time required")
        try:
            session = self.session(now.astimezone(NY).date())
        except CalendarCoverageError:
            return ("CALENDAR_COVERAGE",)
        if session is None or not session.opens_at <= now < session.closes_at:
            return ("OUTSIDE_REGULAR_SESSION",)
        return ()  # Schedule only; never order permission or proof of no halt.
