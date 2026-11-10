"""Admin: see Draw days, send the Founder's OTP, and enter it to run the draw. Nothing else.

There is deliberately no endpoint that redraws, edits or rejects Winners."""

from typing import Annotated

import sqlalchemy as sa
from fastapi import APIRouter, Depends, HTTPException, Path, Request
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app import models as m
from app.deps import get_db, require_admin
from app.drand import round_released_at
from app.drawrun import DrawRefused, run_draw
from app.otp import OtpRefused, active_expiry, request_otp

router = APIRouter(prefix="/api/admin")
Db = Annotated[Session, Depends(get_db)]
Label = Annotated[str, Path(pattern=r"^[A-Za-z0-9-]{1,40}$")]


class OtpEntry(BaseModel):
    code: str = Field(pattern=r"^\d{6}$")


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
        challenge = request_otp(db, day, admin, now, state.otp_sender, state.settings.founder_mobile)
    except OtpRefused as e:
        raise HTTPException(status_code=e.status, detail=e.detail) from e
    return {"sent": True, "expiresAt": _iso(challenge.expires_at)}


@router.post("/draw-days/{label}/run")
def enter_otp_and_run(label: Label, body: OtpEntry, request: Request, db: Db) -> dict:
    admin = require_admin(request, db)
    state = request.app.state
    try:
        day = run_draw(db, label, admin, body.code, state.clock.now(), state.drand_fetch)
    except DrawRefused as e:
        raise HTTPException(status_code=e.status, detail=e.detail) from e
    return day_json(db, day, state.clock.now())
