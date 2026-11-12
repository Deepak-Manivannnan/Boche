"""Draw days and their IST schedule. Every rule about *when* uses the server's clock."""

from datetime import date, datetime, timedelta

import sqlalchemy as sa
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.clock import ist_date, ist_time
from app.db import models as m
from app.draw.drawrun import log_run
from app.draw.lifecycle import close_day
from engine import WINNER_COUNT

ENTRIES_CLOSE = (20, 0)  # 8:00 PM IST: no Ticket can be added, removed or changed after this
DRAW_FROM = (20, 15)  # 8:15 PM IST: the Randomness round is released; the draw may run
PUBLISH_AT = (20, 30)  # 8:30 PM IST: results become visible (or straight after the draw, if later)


def entry_day(now: datetime) -> date:
    """The real Draw day an Entry made now belongs to: today before 8 PM IST, otherwise tomorrow."""
    today = ist_date(now)
    return today if now < ist_time(today, *ENTRIES_CLOSE) else today + timedelta(days=1)


def real_day(db: Session, day: date, *, lock: bool = False) -> m.DrawDay:
    """The real Draw day for a calendar day, created with its schedule the first time it is needed."""
    query = sa.select(m.DrawDay).where(m.DrawDay.label == day.isoformat())
    if lock:
        query = query.with_for_update()
    found = db.scalar(query)
    if found is not None:
        return found
    created = m.DrawDay(
        label=day.isoformat(),
        kind="real",
        day=day,
        status="open",
        closes_at=ist_time(day, *ENTRIES_CLOSE),
        draw_not_before=ist_time(day, *DRAW_FROM),
        publish_not_before=ist_time(day, *PUBLISH_AT),
    )
    savepoint = db.begin_nested()
    db.add(created)
    try:
        savepoint.commit()
    except IntegrityError:  # another request created it at the same moment
        savepoint.rollback()
    return db.scalar(query)


def accepts_entries(day: m.DrawDay, now: datetime) -> bool:
    return day.status == "open" and now < day.closes_at


def entry_draw_day(db: Session, now: datetime) -> m.DrawDay:
    """The real Draw day an Entry made now goes into, locked. Normally entry_day(now); if an Admin has
    already closed that day early (Skip), the Entry goes into the next day instead of being refused."""
    day = real_day(db, entry_day(now), lock=True)
    if not accepts_entries(day, now):
        day = real_day(db, day.day + timedelta(days=1), lock=True)
    return day


# ---------------------------------------------------------------- Skip: today's draw now, not at 8:15 PM


class SkipRefused(Exception):
    def __init__(self, status: int, detail: str):
        super().__init__(detail)
        self.status, self.detail = status, detail


def _issued_count(db: Session, day: m.DrawDay) -> int:
    return db.scalar(
        sa.select(sa.func.count())
        .select_from(m.Ticket)
        .where(m.Ticket.draw_day_id == day.id, m.Ticket.status == "issued")
    )


def can_skip(db: Session, day: m.DrawDay, now: datetime) -> bool:
    return (
        day.kind == "real"
        and accepts_entries(day, now)
        and day.day == ist_date(now)
        and _issued_count(db, day) >= WINNER_COUNT
    )


def skip_to_draw(db: Session, label: str, now: datetime) -> m.DrawDay:
    """An Admin closes today's real Draw day now instead of at 8:00 PM, so its draw can run straight away.

    Same as a late seal (ADR-0002, ADR-0008): the Seal names a drand round at least 30 s in the future, so the
    Ticket list is still fixed before its randomness exists, and the Founder's OTP can be sent once that round
    is out. The result is published straight after the draw. A day already sealed cannot be skipped: its
    Randomness round is in the published Seal and is never changed."""
    day = db.scalar(sa.select(m.DrawDay).where(m.DrawDay.label == label).with_for_update())
    if day is None:
        raise SkipRefused(404, "No such Draw day")
    if day.kind != "real":
        raise SkipRefused(409, "Test days close with Close entries now")
    if not accepts_entries(day, now):
        raise SkipRefused(409, "Entries for this Draw day have already closed")
    if day.day != ist_date(now):
        raise SkipRefused(409, "Only today's draw can be run early")
    if _issued_count(db, day) < WINNER_COUNT:  # sealed with fewer, the draw could never run
        raise SkipRefused(409, f"Today's draw needs at least {WINNER_COUNT} tickets before it can run early")
    day.closes_at = day.draw_not_before = now
    db.commit()
    close_day(db, day.id, now)  # also safe if a tick sealed it in between: it seals once
    day = db.scalar(sa.select(m.DrawDay).where(m.DrawDay.label == label).with_for_update())
    day.publish_not_before = day.draw_not_before
    db.commit()
    return day


# ---------------------------------------------------------------- Reset entries (prototype demos)


class ResetRefused(Exception):
    def __init__(self, status: int, detail: str):
        super().__init__(detail)
        self.status, self.detail = status, detail


def _entered_counts(db: Session, day: m.DrawDay) -> tuple[int, int]:
    """(scratch cards, lucky numbers) entered into this day."""
    cards = db.scalar(sa.select(sa.func.count()).select_from(m.Card).where(m.Card.draw_day_id == day.id))
    tickets = db.scalar(
        sa.select(sa.func.count()).select_from(m.Ticket).where(m.Ticket.draw_day_id == day.id)
    )
    return cards, tickets


def can_reset(db: Session, day: m.DrawDay, now: datetime) -> bool:
    return day.kind == "real" and accepts_entries(day, now) and _entered_counts(db, day)[0] > 0


def reset_entries(db: Session, label: str, admin: m.User, now: datetime) -> m.DrawDay:
    """While a real day still takes entries, give every entered card back to its owner (scratched, not
    entered) so it can be entered again; the day's counts go back to 0. Nothing is drawn, sealed or deleted,
    and orders, cards and lucky numbers stay with their owners. Recorded in the run log."""
    day = db.scalar(sa.select(m.DrawDay).where(m.DrawDay.label == label).with_for_update())
    if day is None:
        raise ResetRefused(404, "No such Draw day")
    if day.kind != "real":
        raise ResetRefused(409, "Only a real day's entries can be reset")
    if not accepts_entries(day, now):
        raise ResetRefused(
            409, "Entries for this Draw day have closed; delete the draw instead once it has run"
        )
    cards, tickets = _entered_counts(db, day)
    if cards == 0:
        raise ResetRefused(409, "No cards have been entered into this draw")
    db.execute(sa.update(m.Ticket).where(m.Ticket.draw_day_id == day.id).values(draw_day_id=None))
    db.execute(
        sa.update(m.Card).where(m.Card.draw_day_id == day.id).values(draw_day_id=None, entered_at=None)
    )
    log_run(db, day, admin, "entries-reset", now, cards=cards, tickets=tickets)
    db.commit()
    db.expire_all()
    return db.scalar(sa.select(m.DrawDay).where(m.DrawDay.label == label))


# ---------------------------------------------------------------- Delete today's draw (ADR-0009)


class DeleteRefused(Exception):
    def __init__(self, status: int, detail: str):
        super().__init__(detail)
        self.status, self.detail = status, detail


def can_delete(day: m.DrawDay, now: datetime) -> bool:
    """Today's real draw, once drawn, until 8:00 PM IST. Reopened later than that, it would close again at
    once with no Tickets and could never be drawn."""
    return (
        day.kind == "real"
        and day.status in ("drawn", "published")
        and day.day == ist_date(now)
        and now < ist_time(day.day, *ENTRIES_CLOSE)
    )


def delete_draw(db: Session, label: str, admin: m.User, now: datetime, publisher) -> m.DrawDay:
    """Erase today's completed draw and reopen the day empty: Winners, Claims, OTPs, the sealed list and its
    Seal on GitHub go; the entered cards go back to their owners to enter again. The day then runs as usual
    (Skip, or close at 8:00 PM). The hash-chained run log keeps a "deleted" entry with what was erased."""
    day = db.scalar(sa.select(m.DrawDay).where(m.DrawDay.label == label).with_for_update())
    if day is None:
        raise DeleteRefused(404, "No such Draw day")
    if not can_delete(day, now):
        if day.kind != "real":
            raise DeleteRefused(409, "Only a real day's draw can be deleted")
        if day.status not in ("drawn", "published"):
            raise DeleteRefused(409, "This draw has not been run yet")
        raise DeleteRefused(409, "Only today's draw can be deleted, before 8:00 PM")

    if publisher is not None:  # first, so a GitHub failure changes nothing
        try:
            publisher.delete(day.label)
        except OSError as e:
            db.rollback()
            raise DeleteRefused(
                502, "Could not remove the Seal from GitHub; nothing was deleted. Try again."
            ) from e

    erased = {
        "fingerprint": day.fingerprint,
        "round": day.drand_round,
        "ticket_count": day.ticket_count,
        "winners": [w["ticket"] for w in day.result.winners] if day.result else [],
    }
    tickets = sa.select(m.Ticket.id).where(m.Ticket.draw_day_id == day.id)
    db.execute(sa.delete(m.Claim).where(m.Claim.ticket_id.in_(tickets.scalar_subquery())))
    db.execute(sa.delete(m.DrawResult).where(m.DrawResult.draw_day_id == day.id))
    db.execute(sa.delete(m.OtpChallenge).where(m.OtpChallenge.draw_day_id == day.id))
    db.execute(sa.update(m.Ticket).where(m.Ticket.draw_day_id == day.id).values(draw_day_id=None))
    db.execute(
        sa.update(m.Card).where(m.Card.draw_day_id == day.id).values(draw_day_id=None, entered_at=None)
    )
    day.status = "open"
    day.closes_at = ist_time(day.day, *ENTRIES_CLOSE)
    day.draw_not_before = ist_time(day.day, *DRAW_FROM)
    day.publish_not_before = ist_time(day.day, *PUBLISH_AT)
    for field in (
        "ticket_count",
        "ticket_csv",
        "fingerprint",
        "drand_round",
        "sealed_at",
        "seal_json",
        "seal_commit_sha",
        "seal_url",
        "drawn_at",
        "published_at",
    ):
        setattr(day, field, None)
    log_run(db, day, admin, "deleted", now, **erased)
    db.commit()
    db.expire_all()
    return db.scalar(sa.select(m.DrawDay).where(m.DrawDay.label == label))
