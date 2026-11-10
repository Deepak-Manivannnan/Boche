"""Public endpoints: anyone can read a closed Draw day's Ticket list and Seal, and trigger due steps."""

from typing import Annotated

import sqlalchemy as sa
from fastapi import APIRouter, Depends, HTTPException, Path, Request
from fastapi.responses import Response
from sqlalchemy.orm import Session

from app import models as m
from app.deps import get_db
from app.lifecycle import advance

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


@router.get("/public/days/{label}/tickets.csv")
def ticket_list(label: Label, db: Db) -> Response:
    day = _closed_day(db, label)
    return Response(
        day.ticket_csv,
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'inline; filename="tickets-{day.label}.csv"'},
    )


@router.get("/public/days/{label}/seal.json")
def seal(label: Label, db: Db) -> Response:
    return Response(_closed_day(db, label).seal_json.encode("utf-8"), media_type="application/json")
