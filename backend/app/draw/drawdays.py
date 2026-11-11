"""Draw days and their IST schedule. Every rule about *when* uses the server's clock."""

from datetime import date, datetime, timedelta

import sqlalchemy as sa
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.clock import ist_date, ist_time
from app.db import models as m

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
