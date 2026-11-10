"""Moving Draw days through their schedule. Safe to call any number of times, from any request: each step
happens once, when it is due (ADR-0005: the free host may be asleep at 8 PM, so nothing relies on a timer).

Step implemented here (ticket 08): Entries close -> the Ticket list is frozen as the canonical CSV, its
Fingerprint and the Randomness round are fixed in the Seal, and the Seal is committed to GitHub."""

import json
import logging
from datetime import datetime

import sqlalchemy as sa
from sqlalchemy.orm import Session, sessionmaker

from app import models as m
from app.drand import CHAIN_HASH, round_for_seal, round_released_at
from app.seals import SealConflict
from engine import SCHEME, canonical_csv, fingerprint

log = logging.getLogger("boche.lifecycle")


def seal_bytes(seal: dict) -> bytes:
    return (json.dumps(seal, indent=2, sort_keys=True) + "\n").encode("utf-8")


def close_day(db: Session, day_id: int, now: datetime) -> bool:
    """Freeze one Draw day's Ticket list. Returns True if this call sealed it."""
    day = db.scalar(sa.select(m.DrawDay).where(m.DrawDay.id == day_id).with_for_update())
    if day is None or day.status != "open" or now < day.closes_at:
        db.rollback()
        return False
    numbers = db.scalars(
        sa.select(m.Ticket.number).where(m.Ticket.draw_day_id == day.id, m.Ticket.status == "issued")
    ).all()
    csv = canonical_csv(numbers)
    round_no = round_for_seal(day.draw_not_before, now)
    seal = {
        "scheme": SCHEME,
        "draw_day": day.label,
        "kind": day.kind,
        "ticket_count": len(numbers),
        "fingerprint": fingerprint(csv),
        "drand": {"chain_hash": CHAIN_HASH, "round": round_no},
        "sealed_at": now.isoformat(),
    }
    day.status, day.sealed_at = "sealed", now
    # After a late seal the round comes out later than 8:15 PM; the draw can't run before it does.
    day.draw_not_before = max(day.draw_not_before, round_released_at(round_no))
    day.ticket_count, day.ticket_csv, day.fingerprint = len(numbers), csv, seal["fingerprint"]
    day.drand_round, day.seal_json = round_no, seal_bytes(seal).decode("utf-8")
    db.commit()
    log.info(
        "sealed %s: %d tickets, fingerprint %s, drand round %d",
        day.label,
        len(numbers),
        seal["fingerprint"],
        round_no,
    )
    return True


def publish_seals(db: Session, publisher) -> tuple[list[str], list[str]]:
    """Commit every Seal not yet on GitHub. Returns (published, still unpublished) labels."""
    pending = db.scalars(
        sa.select(m.DrawDay).where(m.DrawDay.seal_json.is_not(None), m.DrawDay.seal_commit_sha.is_(None))
    ).all()
    published, unpublished = [], []
    for day in pending:
        if publisher is None:
            unpublished.append(day.label)
            continue
        try:
            sha, url = publisher.publish(day.label, day.seal_json.encode("utf-8"))
        except SealConflict:
            log.error("SEAL CONFLICT for %s: GitHub holds a different Seal; not overwriting", day.label)
            unpublished.append(day.label)
            continue
        except OSError as e:
            log.warning("could not publish the Seal for %s yet: %s", day.label, e)
            unpublished.append(day.label)
            continue
        day.seal_commit_sha, day.seal_url = sha or "already-published", url
        db.commit()
        published.append(day.label)
    return published, unpublished


def advance(sessions: sessionmaker, now: datetime, publisher) -> dict:
    with sessions() as db:
        due = db.scalars(
            sa.select(m.DrawDay.id).where(m.DrawDay.status == "open", m.DrawDay.closes_at <= now)
        ).all()
        sealed = []
        for day_id in due:
            if close_day(db, day_id, now):
                sealed.append(db.get(m.DrawDay, day_id).label)
        published, unpublished = publish_seals(db, publisher)
    return {"sealed": sealed, "published": published, "unpublished": unpublished}
