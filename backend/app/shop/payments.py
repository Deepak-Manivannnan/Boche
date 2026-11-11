"""Payment confirmation. Payment itself is mocked (the brief allows it), but confirmation works the way a
real gateway's webhook does: the provider signs the event with a shared secret (HMAC-SHA256), and the
server issues Scratch cards and Tickets only after checking that signature. A repeated event is
recorded once, so retries never create extra Tickets."""

import hashlib
import hmac
import json
import secrets
from dataclasses import dataclass
from datetime import datetime

import sqlalchemy as sa
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.db import models as m
from app.shop.catalog import PACKS
from app.shop.ticketing import unique_numbers

SIGNATURE_HEADER = "X-Mockpay-Signature"


class PaymentRejected(Exception):
    def __init__(self, status: int, detail: str):
        super().__init__(detail)
        self.status, self.detail = status, detail


def sign(secret: str, body: bytes) -> str:
    return "sha256=" + hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()


@dataclass
class MockPaymentProvider:
    """Plays the payment gateway: "charges" an Order and produces the signed event it would send."""

    secret: str

    def capture(self, order: m.Order) -> tuple[bytes, str]:
        event = {
            "event": "payment.captured",
            "provider_ref": "mockpay_" + secrets.token_hex(12),
            "order_id": order.public_id,
            "amount_paise": order.total_paise,
        }
        body = json.dumps(event, separators=(",", ":"), sort_keys=True).encode()
        return body, sign(self.secret, body)


def confirm_payment(db: Session, body: bytes, signature: str | None, secret: str, now: datetime) -> m.Order:
    """Verify a signed payment event and, the first time it is seen, issue the Order's Tickets."""
    if not signature or not hmac.compare_digest(signature, sign(secret, body)):
        raise PaymentRejected(401, "invalid signature")
    try:
        event = json.loads(body)
        ref, order_id, amount = str(event["provider_ref"]), str(event["order_id"]), int(event["amount_paise"])
    except (ValueError, KeyError, TypeError) as e:
        raise PaymentRejected(400, "malformed payment event") from e
    if event.get("event") != "payment.captured":
        raise PaymentRejected(400, "unsupported event")

    order = db.scalar(sa.select(m.Order).where(m.Order.public_id == order_id).with_for_update())
    if order is None:
        raise PaymentRejected(404, "unknown order")
    existing = db.scalar(sa.select(m.Payment).where(m.Payment.provider_ref == ref))
    if existing is not None:
        if existing.order_id != order.id:
            raise PaymentRejected(409, "payment belongs to another order")
        return order  # the same event delivered again: already handled
    if order.status != "pending":
        raise PaymentRejected(409, f"order is already {order.status}")
    if amount != order.total_paise:
        raise PaymentRejected(400, "amount does not match the order")

    db.add(
        m.Payment(order=order, provider_ref=ref, amount_paise=amount, status="confirmed", confirmed_at=now)
    )
    order.status, order.paid_at = "paid", now
    try:
        db.flush()
    except IntegrityError:  # the same event raced in on another connection
        db.rollback()
        return db.scalar(sa.select(m.Order).where(m.Order.public_id == order_id))
    _issue_cards(db, order, now)
    db.commit()
    return order


def _issue_cards(db: Session, order: m.Order, now: datetime) -> None:
    """One Scratch card per Pack bought, each carrying that Pack's number of lucky numbers."""
    cards: list[tuple[m.Card, int]] = []
    for item in sorted(order.items, key=lambda i: list(PACKS).index(i.pack_id)):
        for _ in range(item.qty):
            card = m.Card(public_id=f"{order.public_id}-{len(cards) + 1}", order=order, pack_id=item.pack_id)
            db.add(card)
            cards.append((card, item.numbers_per_pack))
    db.flush()

    def taken(batch: list[str]) -> set[str]:
        return set(db.scalars(sa.select(m.Ticket.number).where(m.Ticket.number.in_(batch))))

    for _attempt in range(5):
        numbers = unique_numbers(sum(n for _, n in cards), already_taken=taken)
        savepoint = db.begin_nested()
        it = iter(numbers)
        for card, n in cards:
            for _ in range(n):
                db.add(m.Ticket(card=card, number=next(it), status="issued", issued_at=now))
        try:
            savepoint.commit()
            return
        except IntegrityError:  # another order took one of these numbers at the same moment
            savepoint.rollback()
    raise RuntimeError("could not issue unique lucky numbers")
