"""Entering a Scratch card into the draw, and refunds (Admin only)."""

import secrets
from typing import Annotated

import sqlalchemy as sa
from fastapi import APIRouter, Depends, HTTPException, Request, Response
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app import models as m
from app.catalog import prize
from app.deps import current_user, get_db, require_admin
from app.drawdays import accepts_entries, entry_day, real_day

router = APIRouter(prefix="/api")
Db = Annotated[Session, Depends(get_db)]


class NewEntry(BaseModel):
    cardId: str = Field(min_length=1, max_length=40)  # noqa: N815 (JSON field name)


def _entry_json(card: m.Card, day: m.DrawDay) -> dict:
    return {"cardId": card.public_id, "drawDay": day.label, "closesAt": day.closes_at.isoformat()}


@router.post("/draw/entries")
def enter_draw(body: NewEntry, request: Request, db: Db) -> dict:
    user = current_user(request, db)
    now = request.app.state.clock.now()
    card = db.scalar(
        sa.select(m.Card)
        .join(m.Order)
        .where(m.Card.public_id == body.cardId, m.Order.user_id == user.id)
        .with_for_update()
    )
    if card is None:
        raise HTTPException(status_code=404, detail="No such card")
    if card.entered_at is not None:  # already entered: same answer, nothing moves
        return _entry_json(card, card.draw_day)
    if card.order.status != "paid":
        raise HTTPException(status_code=409, detail=f"This order is {card.order.status}")

    # Locking the Draw day row means Entries close (ticket 08) can't freeze the list mid-entry.
    day = real_day(db, entry_day(now), lock=True)
    if not accepts_entries(day, now):
        raise HTTPException(status_code=409, detail="This draw is closed for entries")
    card.entered_at, card.draw_day_id = now, day.id
    db.execute(
        sa.update(m.Ticket)
        .where(m.Ticket.card_id == card.id, m.Ticket.status == "issued")
        .values(draw_day_id=day.id)
    )
    db.commit()
    return _entry_json(card, day)


@router.post("/admin/orders/{order_id}/refund")
def refund_order(order_id: str, request: Request, db: Db) -> dict:
    """Refund rules: before Entries close, the Order's Tickets leave the draw. Once a list is closed,
    nothing may leave it, so the refund waits until that Draw day is published. An Order holding a
    Winner can never be refunded."""
    require_admin(request, db)
    now = request.app.state.clock.now()
    order = db.scalar(sa.select(m.Order).where(m.Order.public_id == order_id).with_for_update())
    if order is None:
        raise HTTPException(status_code=404, detail="No such order")
    if order.status != "paid":
        raise HTTPException(status_code=409, detail=f"This order is {order.status}")

    tickets = db.scalars(sa.select(m.Ticket).join(m.Card).where(m.Card.order_id == order.id)).all()
    day_ids = {t.draw_day_id for t in tickets if t.draw_day_id is not None}
    days = db.scalars(sa.select(m.DrawDay).where(m.DrawDay.id.in_(day_ids)).with_for_update()).all()
    numbers = {t.number for t in tickets}
    for day in days:
        if day.status == "published":
            winners = {w["ticket"] for w in (day.result.winners if day.result else [])}
            if winners & numbers:
                raise HTTPException(status_code=409, detail="This order holds a winning ticket")
        elif not accepts_entries(day, now):
            raise HTTPException(
                status_code=409,
                detail=f"The {day.label} draw is closed; refund after its results are published",
            )

    order.status, order.refunded_at = "refunded", now
    for payment in db.scalars(sa.select(m.Payment).where(m.Payment.order_id == order.id)):
        payment.status = "refunded"
    for ticket in tickets:
        if ticket.status == "issued":
            ticket.status, ticket.cancelled_at = "cancelled", now
    db.commit()
    return {"id": order.public_id, "status": order.status, "cancelledTickets": len(tickets)}


class NewClaim(BaseModel):
    cardId: str = Field(min_length=1, max_length=40)  # noqa: N815 (JSON field name)


@router.post("/claims", status_code=201)
def claim_prize(body: NewClaim, request: Request, response: Response, db: Db) -> dict:
    """A Customer claims the prize for a published Winner on one of their cards. One Claim per Ticket."""
    user = current_user(request, db)
    now = request.app.state.clock.now()
    card = db.scalar(
        sa.select(m.Card)
        .join(m.Order)
        .where(m.Card.public_id == body.cardId, m.Order.user_id == user.id)
        .with_for_update()
    )
    if card is None:
        raise HTTPException(status_code=404, detail="No such card")
    day = card.draw_day
    if day is None or day.status != "published" or day.result is None:
        raise HTTPException(status_code=409, detail="This card's draw has no published result yet")
    ranks = {w["ticket"]: w["rank"] for w in day.result.winners}
    winning = [t for t in card.tickets if t.number in ranks]
    if not winning:
        raise HTTPException(status_code=409, detail="This card has no winning ticket")

    existing = db.scalars(sa.select(m.Claim).where(m.Claim.ticket_id.in_([t.id for t in winning]))).all()
    if not existing:
        base = "CLM-" + secrets.token_hex(4).upper()
        for i, t in enumerate(sorted(winning, key=lambda t: ranks[t.number])):
            db.add(
                m.Claim(
                    ticket_id=t.id,
                    user_id=user.id,
                    ref=base if i == 0 else f"{base}-{i + 1}",
                    status="submitted",
                    created_at=now,
                )
            )
        db.commit()
        existing = db.scalars(sa.select(m.Claim).where(m.Claim.ticket_id.in_([t.id for t in winning]))).all()
    else:
        response.status_code = 200
    first = min(existing, key=lambda c: c.id)
    return {
        "cardId": card.public_id,
        "ref": first.ref,
        "ts": int(first.created_at.timestamp() * 1000),
        "amount": sum(prize(ranks[t.number])[1] for t in winning),
    }
