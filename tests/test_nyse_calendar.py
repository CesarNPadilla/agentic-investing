from datetime import UTC, date, datetime, timedelta
from pathlib import Path
import json
import pytest
from pydantic import ValidationError
from market_data.nyse_calendar import NysePublishedCalendar, CalendarCoverageError, PublishedCalendar

PATH = Path(__file__).resolve().parents[1]/"conf/nyse-calendar-2026.json"


@pytest.mark.parametrize("day", json.loads(PATH.read_text())["holidays"])
def test_all_published_holidays_closed(day):
    assert NysePublishedCalendar(PATH).session(date.fromisoformat(day)) is None


@pytest.mark.parametrize("day", [date(2026,11,27), date(2026,12,24)])
def test_early_close_boundaries(day):
    c = NysePublishedCalendar(PATH); s = c.session(day)
    assert s.closes_at.hour == 13 and not s.execution_available
    assert not c.schedule_reasons(s.opens_at)
    assert not c.schedule_reasons(s.closes_at-timedelta(microseconds=1))
    assert c.schedule_reasons(s.closes_at) == ("OUTSIDE_REGULAR_SESSION",)


def test_weekend_holiday_next_day_and_year_end_fail_closed():
    c = NysePublishedCalendar(PATH)
    assert c.next_trading_day(date(2026,7,2)) == date(2026,7,6)
    assert c.next_trading_day(date(2026,11,25)) == date(2026,11,27)
    with pytest.raises(CalendarCoverageError): c.next_trading_day(date(2026,12,31))
    assert c.schedule_reasons(datetime(2027,1,4,15,tzinfo=UTC)) == ("CALENDAR_COVERAGE",)


def test_dst_and_new_york_date_boundaries():
    c = NysePublishedCalendar(PATH)
    assert c.session(date(2026,3,6)).opens_at.astimezone(UTC).hour == 14
    assert c.session(date(2026,3,9)).opens_at.astimezone(UTC).hour == 13
    assert c.session(date(2026,11,2)).opens_at.astimezone(UTC).hour == 14
    assert c.schedule_reasons(datetime(2026,10,6,0,30,tzinfo=UTC)) == ("OUTSIDE_REGULAR_SESSION",)
    with pytest.raises(ValueError): c.schedule_reasons(datetime(2026,10,5,12))


def test_conflicting_and_out_of_coverage_data_rejected():
    raw=json.loads(PATH.read_text())
    raw["early_closes"]["2026-12-25"]="13:00"
    with pytest.raises(ValidationError): PublishedCalendar.model_validate(raw)
    raw["early_closes"]={"2027-01-04":"13:00"}
    with pytest.raises(ValidationError): PublishedCalendar.model_validate(raw)
