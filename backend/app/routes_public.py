"""Public endpoints: anyone can read a closed Draw day's Ticket list and Seal, and trigger due steps."""

from typing import Annotated

import sqlalchemy as sa
from fastapi import APIRouter, Depends, HTTPException, Path, Request
from fastapi.responses import FileResponse, JSONResponse, Response
from sqlalchemy.orm import Session

from app import models as m
from app.config import REPO_ROOT
from app.deps import get_db
from app.lifecycle import advance
from app.results import result_json, winners_public

router = APIRouter(prefix="/api")
Db = Annotated[Session, Depends(get_db)]
Label = Annotated[str, Path(pattern=r"^[A-Za-z0-9-]{1,40}$")]


@router.post("/tick")
def tick(request: Request) -> dict:
    """Apply any Draw day step that is due. Called by an external scheduler at 8:00, 8:15 and 8:30 PM IST;
    every other API request does the same, so this only matters while the site is otherwise idle."""
    state = request.app.state
    return advance(state.sessionmaker, state.clock.now(), state.seal_publisher)


def _closed_day(db: Session, label: str) -> m.DrawDay:
    day = db.scalar(sa.select(m.DrawDay).where(m.DrawDay.label == label))
    if day is None or day.seal_json is None:
        raise HTTPException(status_code=404, detail="This Draw day has not closed yet")
    return day


def _download(name: str, label: str) -> dict:
    """Save as e.g. tickets-2026-11-10.csv; the Verifier accepts that name as well as tickets.csv."""
    stem, ext = name.split(".")
    return {"Content-Disposition": f'attachment; filename="{stem}-{label}.{ext}"'}


@router.get("/public/days/{label}/tickets.csv")
def ticket_list(label: Label, db: Db) -> Response:
    day = _closed_day(db, label)
    return Response(
        day.ticket_csv, media_type="text/csv; charset=utf-8", headers=_download("tickets.csv", day.label)
    )


@router.get("/public/days/{label}/seal.json")
def seal(label: Label, db: Db) -> Response:
    day = _closed_day(db, label)
    return Response(
        day.seal_json.encode("utf-8"),
        media_type="application/json",
        headers=_download("seal.json", day.label),
    )


@router.get("/public/days/{label}/result.json")
def result(label: Label, db: Db) -> JSONResponse:
    day = db.scalar(sa.select(m.DrawDay).where(m.DrawDay.label == label))
    if day is None or day.status != "published":
        raise HTTPException(status_code=404, detail="The result of this Draw day is not published yet")
    return JSONResponse(result_json(db, day), headers=_download("result.json", day.label))


@router.get("/public/days")
def recent_days(db: Db) -> list[dict]:
    """The last 30 Draw days that have closed, newest first, with Winners once published."""
    days = db.scalars(
        sa.select(m.DrawDay)
        .where(m.DrawDay.seal_json.is_not(None))
        .order_by(m.DrawDay.day.desc(), m.DrawDay.id.desc())
        .limit(30)
    ).all()
    return [
        {
            "label": d.label,
            "kind": d.kind,
            "day": d.day.isoformat(),
            "status": d.status,
            "ticketCount": d.ticket_count,
            "fingerprint": d.fingerprint,
            "drandRound": d.drand_round,
            "sealUrl": d.seal_url,
            "publishNotBefore": d.publish_not_before.isoformat(),
            "publishedAt": d.published_at.isoformat() if d.published_at else None,
            "winners": winners_public(db, d) if d.status == "published" else None,
        }
        for d in days
    ]


@router.get("/public/verifier/verify.py")
def download_verifier() -> FileResponse:
    """The standalone Verifier, byte for byte as in the repository (verifier/verify.py)."""
    return FileResponse(
        REPO_ROOT / "verifier" / "verify.py", media_type="text/x-python; charset=utf-8", filename="verify.py"
    )
