"""Time for the server. Every rule that depends on the time (Entries close, draw, Publish) asks a
Clock, so tests can set the time exactly. Times are aware UTC; Draw day rules are in IST."""

from datetime import UTC, date, datetime, time, timedelta, timezone
from typing import Protocol

IST = timezone(timedelta(hours=5, minutes=30), "IST")


class Clock(Protocol):
    def now(self) -> datetime: ...


class SystemClock:
    def now(self) -> datetime:
        return datetime.now(UTC)


class FixedClock:
    """A clock for tests: stays at the time it is given until moved."""

    def __init__(self, at: datetime):
        self._at = _aware(at)

    def now(self) -> datetime:
        return self._at

    def set(self, at: datetime) -> None:
        self._at = _aware(at)

    def advance(self, **delta: float) -> None:
        self._at += timedelta(**delta)


def ist_time(day: date, hour: int, minute: int = 0) -> datetime:
    """The UTC instant of a wall-clock time in IST on a calendar day."""
    return datetime.combine(day, time(hour, minute), IST).astimezone(UTC)


def ist_date(at: datetime) -> date:
    """The IST calendar day an instant falls on."""
    return _aware(at).astimezone(IST).date()


def _aware(at: datetime) -> datetime:
    if at.tzinfo is None:
        raise ValueError("times must carry a timezone")
    return at.astimezone(UTC)
