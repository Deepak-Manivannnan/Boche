"""Buying tea: create an Order, pay for it (mock), list my Orders, scratch a card."""

import re
import secrets
from typing import Annotated

import sqlalchemy as sa
from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field, StrictInt, field_validator
from sqlalchemy.orm import Session, selectinload

from app.core.deps import current_user, get_db
from app.db import models as m
from app.shop.catalog import LOGISTICS_GST_RATE, MAX_QTY, PACKS, TEA_GST_RATE, prize, quote
from app.shop.payments import SIGNATURE_HEADER, MockPaymentProvider, PaymentRejected, confirm_payment

router = APIRouter(prefix="/api")
Db = Annotated[Session, Depends(get_db)]
ORDER_ID_ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"


class Delivery(BaseModel):
    name: str = Field(min_length=2, max_length=100)
    house: str = Field(min_length=1, max_length=200)
    street: str = Field(min_length=1, max_length=200)
    pin: str
    po: str = Field(default="", max_length=100)
    district: str = Field(min_length=1, max_length=100)

    @field_validator("pin")
    @classmethod
    def kerala_pincode(cls, v: str) -> str:
        if not re.fullmatch(r"\d{6}", v) or not 670000 <= int(v) <= 695999:
            raise ValueError("we deliver only to Kerala pincodes (670001 - 695999)")
        return v


class NewOrder(BaseModel):
    # Extra fields (a price, a ticket count...) are ignored: the server prices every Order itself.
    items: dict[str, Annotated[StrictInt, Field(ge=0, le=MAX_QTY)]]
    delivery: Delivery

    @field_validator("items")
    @classmethod
    def known_packs_and_not_empty(cls, items: dict[str, int]) -> dict[str, int]:
        quote(items)  # raises ValueError for unknown packs or an empty bag
        return items


def _new_order_id() -> str:
    return "TEA-" + "".join(secrets.choice(ORDER_ID_ALPHABET) for _ in range(8))


def _my_order(db: Session, user: m.User, order_id: str) -> m.Order:
    order = db.scalar(
        sa.select(m.Order)
        .where(m.Order.public_id == order_id, m.Order.user_id == user.id)
        .options(
            selectinload(m.Order.items),
            selectinload(m.Order.cards).selectinload(m.Card.tickets),
            selectinload(m.Order.cards).selectinload(m.Card.draw_day).selectinload(m.DrawDay.result),
        )
    )
    if order is None:
        raise HTTPException(status_code=404, detail="No such order")
    return order


def order_json(order: m.Order, claims: dict[int, m.Claim] | None = None) -> dict:
    when = order.paid_at or order.created_at
    return {
        "id": order.public_id,
        "status": order.status,
        "ts": int(when.timestamp() * 1000),
        "createdAt": order.created_at.isoformat(),
        "paidAt": order.paid_at.isoformat() if order.paid_at else None,
        "items": [
            {
                "packId": i.pack_id,
                "size": PACKS[i.pack_id].size,
                "qty": i.qty,
                "unitPricePaise": i.unit_price_paise,
                "numbersPerPack": i.numbers_per_pack,
            }
            for i in sorted(order.items, key=lambda i: list(PACKS).index(i.pack_id))
        ],
        "subtotalPaise": order.subtotal_paise,
        "logisticsPaise": order.logistics_paise,
        "teaGstPaise": order.tea_gst_paise,
        "logisticsGstPaise": order.logistics_gst_paise,
        "gstPaise": order.gst_paise,
        "totalPaise": order.total_paise,
        "teaGstRate": TEA_GST_RATE,
        "logisticsGstRate": LOGISTICS_GST_RATE,
        "delivery": order.delivery,
        "cards": [
            {
                "id": c.public_id,
                "packId": c.pack_id,
                "size": PACKS[c.pack_id].size,
                "numbers": [t.number for t in sorted(c.tickets, key=lambda t: t.id)],
                "scratched": c.scratched_at is not None,
                "entered": c.entered_at is not None,
                "drawDay": c.draw_day.label if c.draw_day else None,
                **card_result(c, claims or {}),
            }
            for c in sorted(order.cards, key=lambda c: c.id)
        ],
    }


def card_result(card: m.Card, claims: dict[int, m.Claim]) -> dict:
    """Per card: was it in its Draw day's sealed list, which of its Tickets won (only once published),
    and the Claim, if any."""
    day = card.draw_day
    included = None
    if day is not None and day.sealed_at is not None:
        included = any(
            t.draw_day_id == day.id and (t.cancelled_at is None or t.cancelled_at > day.sealed_at)
            for t in card.tickets
        )
    wins = []
    if day is not None and day.status == "published" and day.result is not None:
        ranks = {w["ticket"]: w["rank"] for w in day.result.winners}
        for t in card.tickets:
            if t.number in ranks:
                label, amount = prize(ranks[t.number])
                wins.append({"ticket": t.number, "rank": ranks[t.number], "label": label, "amount": amount})
        wins.sort(key=lambda w: w["rank"])
    mine = sorted((claims[t.id] for t in card.tickets if t.id in claims), key=lambda c: c.id)
    claim = None
    if mine:
        claim = {
            "ref": mine[0].ref,
            "ts": int(mine[0].created_at.timestamp() * 1000),
            "amount": sum(w["amount"] for w in wins),
        }
    return {"included": included, "wins": wins, "claim": claim}


@router.post("/orders", status_code=201)
def create_order(body: NewOrder, request: Request, db: Db) -> dict:
    user = current_user(request, db)
    q = quote(body.items)
    order = m.Order(
        public_id=_new_order_id(),
        user=user,
        status="pending",
        subtotal_paise=q.subtotal_paise,
        logistics_paise=q.logistics_paise,
        tea_gst_paise=q.tea_gst_paise,
        logistics_gst_paise=q.logistics_gst_paise,
        gst_paise=q.gst_paise,
        total_paise=q.total_paise,
        delivery=body.delivery.model_dump(),
        created_at=request.app.state.clock.now(),
    )
    order.items = [
        m.OrderItem(pack_id=p.id, qty=qty, unit_price_paise=p.price_paise, numbers_per_pack=p.numbers)
        for p, qty in q.lines
    ]
    db.add(order)
    db.commit()
    return order_json(order)


@router.post("/payments/mock/{order_id}/pay")
def pay_with_mock_provider(order_id: str, request: Request, db: Db) -> dict:
    """The customer completes the (simulated) UPI payment. The mock provider sends its signed event
    through exactly the same check as the public webhook."""
    user = current_user(request, db)
    order = _my_order(db, user, order_id)
    if order.status == "pending":
        body, signature = MockPaymentProvider(request.app.state.settings.payment_secret).capture(order)
        _confirm(db, request, body, signature)
        db.expire_all()
        order = _my_order(db, user, order_id)
    return order_json(order)


@router.post("/payments/webhook")
async def payment_webhook(request: Request, db: Db) -> dict:
    body = await request.body()
    order = _confirm(db, request, body, request.headers.get(SIGNATURE_HEADER))
    return {"order": order.public_id, "status": order.status}


def _confirm(db: Session, request: Request, body: bytes, signature: str | None) -> m.Order:
    try:
        return confirm_payment(
            db, body, signature, request.app.state.settings.payment_secret, request.app.state.clock.now()
        )
    except PaymentRejected as e:
        db.rollback()
        raise HTTPException(status_code=e.status, detail=e.detail) from e


@router.get("/me/orders")
def my_orders(request: Request, db: Db) -> list[dict]:
    user = current_user(request, db)
    orders = db.scalars(
        sa.select(m.Order)
        .where(m.Order.user_id == user.id, m.Order.status != "pending")
        .order_by(m.Order.paid_at.desc(), m.Order.id.desc())
        .options(
            selectinload(m.Order.items),
            selectinload(m.Order.cards).selectinload(m.Card.tickets),
            selectinload(m.Order.cards).selectinload(m.Card.draw_day).selectinload(m.DrawDay.result),
        )
    ).all()
    ticket_ids = [t.id for o in orders for c in o.cards for t in c.tickets]
    found = db.scalars(sa.select(m.Claim).where(m.Claim.ticket_id.in_(ticket_ids)))
    claims = {cl.ticket_id: cl for cl in found}
    return [order_json(o, claims) for o in orders]


@router.post("/cards/{card_id}/scratch")
def scratch_card(card_id: str, request: Request, db: Db) -> dict:
    user = current_user(request, db)
    card = db.scalar(
        sa.select(m.Card).join(m.Order).where(m.Card.public_id == card_id, m.Order.user_id == user.id)
    )
    if card is None:
        raise HTTPException(status_code=404, detail="No such card")
    if card.scratched_at is None:
        card.scratched_at = request.app.state.clock.now()
        db.commit()
    return {"id": card.public_id, "scratched": True}
