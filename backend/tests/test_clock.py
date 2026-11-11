from datetime import UTC, date, datetime, timedelta

import pytest

from app.core.clock import IST, FixedClock, SystemClock, ist_date, ist_time


def test_system_clock_returns_an_aware_utc_time():
    now = SystemClock().now()
    assert now.tzinfo is not None
    assert now.utcoffset() == timedelta(0)


def test_fixed_clock_returns_the_time_it_was_given_and_can_advance():
    clock = FixedClock(datetime(2026, 11, 10, 14, 29, 59, tzinfo=UTC))
    assert clock.now() == datetime(2026, 11, 10, 14, 29, 59, tzinfo=UTC)
    clock.advance(seconds=1)
    assert clock.now() == datetime(2026, 11, 10, 14, 30, tzinfo=UTC)


def test_fixed_clock_refuses_a_naive_time():
    with pytest.raises(ValueError):
        FixedClock(datetime(2026, 11, 10, 20, 0))


def test_eight_pm_ist_is_two_thirty_pm_utc():
    assert ist_time(date(2026, 11, 10), 20, 0) == datetime(2026, 11, 10, 14, 30, tzinfo=UTC)


def test_the_ist_calendar_day_changes_at_midnight_ist_not_utc():
    just_before = datetime(2026, 11, 10, 18, 29, 59, tzinfo=UTC)  # 23:59:59 IST
    just_after = datetime(2026, 11, 10, 18, 30, 0, tzinfo=UTC)  # 00:00:00 IST next day
    assert ist_date(just_before) == date(2026, 11, 10)
    assert ist_date(just_after) == date(2026, 11, 11)


def test_ist_is_five_and_a_half_hours_ahead_of_utc():
    assert datetime(2026, 1, 1, tzinfo=IST).utcoffset() == timedelta(hours=5, minutes=30)
