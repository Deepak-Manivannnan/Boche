"""Running a Draw day's draw, exactly once (ADR-0001).

The only inputs are the Ticket list frozen when Entries closed and the drand Randomness round named in
the Seal. The OTP gates *when* this runs; nothing an Admin sends reaches the engine. The result is saved
with a unique constraint per Draw day, so a repeat, a race or a restart after a crash returns the same
saved result. Every attempt is appended to a hash-chained run log for audit."""

import hashlib
import json
from datetime import UTC, datetime

import sqlalchemy as sa
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app import models as m
from app.drand import DrandUnavailable
from app.otp import OtpRefused, check_otp
from engine import pick_winners

GENESIS_HASH = "0" * 64


class DrawRefused(Exception):
    def __init__(self, status: int, detail: str):
        super().__init__(detail)
        self.status, self.detail = status, detail


def entry_hash(
    prev_hash: str,
    seq: int,
    draw_day_id: int,
    actor: int | None,
    outcome: str,
    at: datetime,
    detail: str | None,
) -> str:
    text = "|".join(
        [prev_hash, str(seq), str(draw_day_id), str(actor or ""), outcome, at.isoformat(), detail or ""]
    )
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def verify_chain(rows) -> bool:
    """True if every run-log entry links to the one before and its hash matches its contents."""
    prev = GENESIS_HASH
    for r in rows:
        at = r.at if r.at.tzinfo else r.at.replace(tzinfo=UTC)
        if r.prev_hash != prev or r.entry_hash != entry_hash(
            prev, r.seq, r.draw_day_id, r.actor_user_id, r.outcome, at, r.detail
        ):
            return False
        prev = r.entry_hash
    return True


def log_run(db: Session, day: m.DrawDay, actor: m.User | None, outcome: str, now: datetime, **detail) -> None:
    for _ in range(5):
        last = db.scalar(sa.select(m.DrawRun).order_by(m.DrawRun.seq.desc()).limit(1))
        seq, prev = (last.seq + 1, last.entry_hash) if last else (1, GENESIS_HASH)
        text = json.dumps(detail, sort_keys=True, separators=(",", ":"))
        actor_id = actor.id if actor else None
        row = m.DrawRun(
            seq=seq,
            draw_day_id=day.id,
            actor_user_id=actor_id,
            outcome=outcome,
            detail=text,
            at=now,
            prev_hash=prev,
            entry_hash=entry_hash(prev, seq, day.id, actor_id, outcome, now, text),
        )
        savepoint = db.begin_nested()
        db.add(row)
        try:
            savepoint.commit()
            return
        except IntegrityError:  # another run log entry took this position; read the new end and retry
            savepoint.rollback()
    raise RuntimeError("could not append to the draw run log")


def sealed_tickets(day: m.DrawDay) -> list[str]:
    return [line.split(",", 1)[1] for line in day.ticket_csv.decode("utf-8").splitlines()[1:]]


def run_draw(db: Session, label: str, admin: m.User, code: str, now: datetime, fetch_drand) -> m.DrawDay:
    day = db.scalar(sa.select(m.DrawDay).where(m.DrawDay.label == label).with_for_update())
    if day is None or day.seal_json is None:
        raise DrawRefused(404, "This Draw day has not closed yet")
    if day.result is not None:
        log_run(db, day, admin, "repeat", now, note="already drawn; saved result returned")
        db.commit()
        return day
    if now < day.draw_not_before:
        raise DrawRefused(409, "The Randomness round is not released yet")
    try:
        challenge = check_otp(db, day, code, now)
    except OtpRefused as e:
        raise DrawRefused(e.status, e.detail) from e

    try:
        drand = fetch_drand(day.drand_round)
        if (
            int(drand["round"]) != day.drand_round
            or hashlib.sha256(bytes.fromhex(drand["signature"])).hexdigest() != drand["randomness"]
        ):
            raise DrandUnavailable("drand answer does not match the sealed round")
        result = pick_winners(sealed_tickets(day), drand["randomness"], day.label)
        if result.fingerprint != day.fingerprint:
            raise RuntimeError("the stored Ticket list does not match its Fingerprint")
    except DrandUnavailable as e:
        _log_failure(db, day.id, admin, now, str(e))
        raise DrawRefused(503, "drand is unavailable; nothing was drawn. Try again in a minute.") from e
    except Exception as e:
        _log_failure(db, day.id, admin, now, f"{type(e).__name__}: {e}")
        raise DrawRefused(500, "The draw run failed and nothing was saved. Try again.") from e

    winners = [
        {"rank": x.rank, "prize": x.prize, "position": x.position, "ticket": x.ticket} for x in result.winners
    ]
    db.add(
        m.DrawResult(
            draw_day_id=day.id,
            randomness=drand["randomness"],
            signature=drand["signature"],
            seed=result.seed,
            winners=winners,
            created_at=now,
        )
    )
    day.status, day.drawn_at = "drawn", now
    challenge.consumed_at = now
    log_run(
        db,
        day,
        admin,
        "completed",
        now,
        round=day.drand_round,
        randomness=drand["randomness"],
        fingerprint=day.fingerprint,
        seed=result.seed,
        winners=[x["ticket"] for x in winners],
    )
    try:
        db.commit()
    except IntegrityError:  # another request saved this Draw day's result first; it is the same result
        db.rollback()
    db.expire_all()
    return db.scalar(sa.select(m.DrawDay).where(m.DrawDay.label == label))


def _log_failure(db: Session, day_id: int, admin: m.User, now: datetime, error: str) -> None:
    db.rollback()  # nothing from the failed run is kept; the OTP stays valid
    day = db.get(m.DrawDay, day_id)
    log_run(db, day, admin, "failed", now, error=error)
    db.commit()
