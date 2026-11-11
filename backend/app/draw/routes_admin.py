"""Admin: see Draw days, send the Founder's OTP, and enter it to run the draw. Nothing else.

There is deliberately no endpoint that redraws, edits or rejects Winners."""

import threading
from datetime import timedelta
from typing import Annotated

import sqlalchemy as sa
from fastapi import APIRouter, Depends, HTTPException, Path, Request
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.core.deps import get_db, require_admin
from app.db import models as m
from app.draw.drand import round_released_at
from app.draw.drawrun import DrawRefused, run_draw
from app.draw.lifecycle import publish_results, publish_seals
from app.draw.otp import OtpRefused, active_expiry, request_otp
from app.draw.testmode import TestModeRefused, close_test_day, create_test_day, seed_tickets, test_day

router = APIRouter(prefix="/api/admin")
Db = Annotated[Session, Depends(get_db)]
Label = Annotated[str, Path(pattern=r"^[A-Za-z0-9-]{1,40}$")]


class OtpEntry(BaseModel):
    code: str = Field(pattern=r"^\d{4}$")


# Seeding runs on the server, one job per Test day: a click adds exactly the asked-for number of Tickets,
# whatever the browser does meanwhile (refresh, close, slow network). A second job waits for the first.
SEED_BATCH = 500
_seed_jobs: dict[str, dict] = {}
_seed_lock = threading.Lock()


def _seed_job_json(label: str) -> dict | None:
    job = _seed_jobs.get(label)
    return dict(job) if job else None


def _run_seed_job(state, label: str) -> None:
    job = _seed_jobs[label]
    try:
        while job["done"] < job["target"]:
            step = min(SEED_BATCH, job["target"] - job["done"])
            with state.sessionmaker() as db:
                seed_tickets(db, label, step, state.clock.now(), state.settings.payment_secret)
            job["done"] += step
    except Exception as e:  # noqa: BLE001 - shown to the Admin; the Tickets added so far stay
        job["error"] = getattr(e, "detail", None) or "Seeding stopped"
    finally:
        job["running"] = False


def _iso(t):
    return t.isoformat() if t else None


def day_json(db: Session, day: m.DrawDay, now) -> dict:
    count = day.ticket_count
    if count is None:
        count = db.scalar(
            sa.select(sa.func.count())
            .select_from(m.Ticket)
            .where(m.Ticket.draw_day_id == day.id, m.Ticket.status == "issued")
        )
    otp_until = active_expiry(db, day, now) if day.status == "sealed" else None
    return {
        "label": day.label,
        "kind": day.kind,
        "status": day.status,
        "ticketCount": count,
        "closesAt": _iso(day.closes_at),
        "drawNotBefore": _iso(day.draw_not_before),
        "publishNotBefore": _iso(day.publish_not_before),
        "sealedAt": _iso(day.sealed_at),
        "fingerprint": day.fingerprint,
        "drandRound": day.drand_round,
        "roundReleasedAt": _iso(round_released_at(day.drand_round)) if day.drand_round else None,
        "sealUrl": day.seal_url,
        "sealPublished": bool(day.seal_commit_sha),
        "canRequestOtp": day.status == "sealed" and now >= day.draw_not_before,
        "otpExpiresAt": _iso(otp_until),
        "drawnAt": _iso(day.drawn_at),
        "randomness": day.result.randomness if day.result else None,
        "winners": day.result.winners if day.result else None,
        "seeding": _seed_job_json(day.label),
    }


def _day(db: Session, label: str) -> m.DrawDay:
    day = db.scalar(sa.select(m.DrawDay).where(m.DrawDay.label == label))
    if day is None:
        raise HTTPException(status_code=404, detail="No such Draw day")
    return day


@router.get("/draw-days")
def list_days(request: Request, db: Db) -> list[dict]:
    require_admin(request, db)
    now = request.app.state.clock.now()
    days = db.scalars(
        sa.select(m.DrawDay).order_by(m.DrawDay.day.desc(), m.DrawDay.id.desc()).limit(14)
    ).all()
    return [day_json(db, d, now) for d in days]


@router.get("/draw-days/{label}")
def get_day(label: Label, request: Request, db: Db) -> dict:
    require_admin(request, db)
    return day_json(db, _day(db, label), request.app.state.clock.now())


@router.post("/draw-days/{label}/otp")
def send_founder_otp(label: Label, request: Request, db: Db) -> dict:
    admin = require_admin(request, db)
    state, now = request.app.state, request.app.state.clock.now()
    day = _day(db, label)
    if day.seal_json is None:
        raise HTTPException(status_code=404, detail="This Draw day has not closed yet")
    if day.status != "sealed":
        raise HTTPException(status_code=409, detail="This Draw day has already been drawn")
    if now < day.draw_not_before:
        raise HTTPException(status_code=409, detail="The Randomness round is not released yet")
    try:
        challenge = request_otp(
            db,
            day,
            admin,
            now,
            state.otp_sender,
            state.settings.founder_mobile,
            timedelta(minutes=state.settings.otp_expiry_minutes),
        )
    except OtpRefused as e:
        raise HTTPException(status_code=e.status, detail=e.detail) from e
    return {"sent": True, "expiresAt": _iso(challenge.expires_at)}  # the code only goes to the Founder


@router.post("/draw-days/{label}/run")
def enter_otp_and_run(label: Label, body: OtpEntry, request: Request, db: Db) -> dict:
    admin = require_admin(request, db)
    state = request.app.state
    try:
        day = run_draw(db, label, admin, body.code, state.clock.now(), state.drand_fetch)
        publish_results(db, state.clock.now())  # a draw after 8:30 PM is published straight away
        db.refresh(day)
    except DrawRefused as e:
        raise HTTPException(status_code=e.status, detail=e.detail) from e
    return day_json(db, day, state.clock.now())


# ---------------------------------------------------------------- test mode


class Seed(BaseModel):
    count: int = Field(ge=1)


class Close(BaseModel):
    publishGapMinutes: int = Field(default=0, ge=0, le=120)  # noqa: N815 (JSON field name)


def _refused(e: TestModeRefused) -> HTTPException:
    return HTTPException(status_code=e.status, detail=e.detail)


@router.post("/test-days", status_code=201)
def new_test_day(request: Request, db: Db) -> dict:
    require_admin(request, db)
    now = request.app.state.clock.now()
    exists = getattr(request.app.state.seal_publisher, "exists", None)

    def taken(label: str) -> bool:  # GitHub unreachable: the label is still free in this database
        try:
            return bool(exists and exists(label))
        except OSError:
            return False

    return day_json(db, create_test_day(db, now, taken), now)


@router.post("/test-days/{label}/seed")
def seed_test_day(label: Label, body: Seed, request: Request, db: Db) -> dict:
    require_admin(request, db)
    state = request.app.state
    try:
        total = seed_tickets(db, label, body.count, state.clock.now(), state.settings.payment_secret)
    except TestModeRefused as e:
        raise _refused(e) from e
    return {"label": label, "ticketCount": total}


@router.post("/test-days/{label}/seed-job", status_code=202)
def start_seed_job(label: Label, body: Seed, request: Request, db: Db) -> dict:
    """Start adding `count` Tickets in the background; progress shows in the day's "seeding" field."""
    require_admin(request, db)
    try:
        day = test_day(db, label)
    except TestModeRefused as e:
        raise _refused(e) from e
    if day.status != "open":
        raise HTTPException(status_code=409, detail="This Test day is closed")
    with _seed_lock:
        job = _seed_jobs.get(label)
        if job and job["running"]:
            raise HTTPException(status_code=409, detail="Tickets are already being added to this Test day")
        _seed_jobs[label] = {"target": body.count, "done": 0, "running": True, "error": None}
    threading.Thread(target=_run_seed_job, args=(request.app.state, label), daemon=True).start()
    return _seed_job_json(label)


@router.post("/test-days/{label}/close")
def close_now(label: Label, body: Close, request: Request, db: Db) -> dict:
    require_admin(request, db)
    state, now = request.app.state, request.app.state.clock.now()
    try:
        day = close_test_day(db, label, now, timedelta(minutes=body.publishGapMinutes))
    except TestModeRefused as e:
        raise _refused(e) from e
    publish_seals(db, state.seal_publisher)
    db.refresh(day)
    return day_json(db, day, now)
