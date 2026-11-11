"""Test mode: run a whole Draw day on demand (ticket 12).

A Test day is a separate Draw day (kind "test", label "test-1", "test-2", …). It is seeded through the real
issuing path (priced Orders, a signed mock-payment confirmation, server-generated lucky numbers) and then uses the
same Seal, Founder OTP, draw and publish code as a real day. Nothing here can select or change a real Draw
day: every function refuses a day whose kind is not "test"."""

import re
import secrets
from collections.abc import Callable
from datetime import datetime, timedelta

import sqlalchemy as sa
from sqlalchemy.orm import Session

from app.core.clock import IST
from app.db import models as m
from app.draw.lifecycle import close_day
from app.shop.catalog import MAX_QTY, quote
from app.shop.payments import MockPaymentProvider, confirm_payment

FAR_FUTURE = timedelta(days=3650)  # a Test day only closes when an Admin says so
TEST_CUSTOMERS = 20
MAX_SEED_PER_CALL = 5000


class TestModeRefused(Exception):
    def __init__(self, status: int, detail: str):
        super().__init__(detail)
        self.status, self.detail = status, detail


def create_test_day(db: Session, now: datetime, taken: Callable[[str], bool] | None = None) -> m.DrawDay:
    """Labels run test-1, test-2, …: one past the highest number used so far, skipping any label `taken`
    reports as already used elsewhere (a Seal file on GitHub from another environment)."""
    local = now.astimezone(IST)
    used = db.scalars(sa.select(m.DrawDay.label).where(m.DrawDay.kind == "test")).all()
    n = max([int(x[5:]) for x in used if re.fullmatch(r"test-\d+", x)] or [0]) + 1
    while taken and taken(f"test-{n}"):
        n += 1
    label = f"test-{n}"
    day = m.DrawDay(
        label=label,
        kind="test",
        day=local.date(),
        status="open",
        closes_at=now + FAR_FUTURE,
        draw_not_before=now + FAR_FUTURE,
        publish_not_before=now + FAR_FUTURE,
    )
    db.add(day)
    db.commit()
    return day


def test_day(db: Session, label: str, *, lock: bool = False) -> m.DrawDay:
    query = sa.select(m.DrawDay).where(m.DrawDay.label == label, m.DrawDay.kind == "test")
    day = db.scalar(query.with_for_update() if lock else query)
    if day is None:
        raise TestModeRefused(404, "No such Test day")
    return day


def _test_customers(db: Session, now: datetime) -> list[m.User]:
    users = db.scalars(
        sa.select(m.User).where(m.User.google_sub.like("test-customer-%")).order_by(m.User.id)
    ).all()
    for i in range(len(users), TEST_CUSTOMERS):
        db.add(
            m.User(
                google_sub=f"test-customer-{i + 1}",
                email=f"test-customer-{i + 1}@boche.test",
                name=f"Test Customer{i + 1}",
                role="customer",
                created_at=now,
            )
        )
    db.commit()
    return db.scalars(
        sa.select(m.User).where(m.User.google_sub.like("test-customer-%")).order_by(m.User.id)
    ).all()


def _baskets(count: int):
    """Packs adding up to exactly `count` Tickets: 1 kg packs (8 each), then 250 g packs (1 each)."""
    while count > 0:
        if count >= 8:
            qty = min(MAX_QTY, count // 8)
            yield {"p1k": qty}
            count -= 8 * qty
        else:
            yield {"p250": count}
            count = 0


def seed_tickets(db: Session, label: str, count: int, now: datetime, payment_secret: str) -> int:
    """Add `count` paid, entered Tickets to an open Test day. Returns the day's Ticket count."""
    if not 1 <= count <= MAX_SEED_PER_CALL:
        raise TestModeRefused(422, f"Seed between 1 and {MAX_SEED_PER_CALL} tickets per call")
    day = test_day(db, label)
    if day.status != "open":
        raise TestModeRefused(409, "This Test day is closed")
    customers = _test_customers(db, now)
    provider = MockPaymentProvider(payment_secret)
    for i, items in enumerate(_baskets(count)):
        q = quote(items)
        order = m.Order(
            public_id="TEA-T" + secrets.token_hex(4).upper(),
            user=customers[i % len(customers)],
            status="pending",
            subtotal_paise=q.subtotal_paise,
            logistics_paise=q.logistics_paise,
            tea_gst_paise=q.tea_gst_paise,
            logistics_gst_paise=q.logistics_gst_paise,
            gst_paise=q.gst_paise,
            total_paise=q.total_paise,
            delivery={
                "name": "Test Customer",
                "house": "Test",
                "street": "Test",
                "pin": "682001",
                "po": "",
                "district": "Ernakulam",
            },
            created_at=now,
        )
        order.items = [
            m.OrderItem(pack_id=p.id, qty=n, unit_price_paise=p.price_paise, numbers_per_pack=p.numbers)
            for p, n in q.lines
        ]
        db.add(order)
        db.commit()
        body, signature = provider.capture(order)
        confirm_payment(
            db, body, signature, payment_secret, now
        )  # the real path: signed, then Tickets issued
        card_ids = db.scalars(sa.select(m.Card.id).where(m.Card.order_id == order.id)).all()
        db.execute(
            sa.update(m.Card).where(m.Card.id.in_(card_ids)).values(entered_at=now, draw_day_id=day.id)
        )
        db.execute(sa.update(m.Ticket).where(m.Ticket.card_id.in_(card_ids)).values(draw_day_id=day.id))
        db.commit()
    return db.scalar(
        sa.select(sa.func.count())
        .select_from(m.Ticket)
        .where(m.Ticket.draw_day_id == day.id, m.Ticket.status == "issued")
    )


def close_test_day(db: Session, label: str, now: datetime, publish_gap: timedelta) -> m.DrawDay:
    """Entries close now. The Seal names the next drand round at least 30 s ahead (as for a late real seal);
    the result is published `publish_gap` after that round, or straight after the draw if later."""
    day = test_day(db, label, lock=True)
    if day.status != "open":
        raise TestModeRefused(409, "This Test day is already closed")
    if (day.ticket_count or 0) == 0 and not db.scalar(
        sa.select(sa.func.count()).select_from(m.Ticket).where(m.Ticket.draw_day_id == day.id)
    ):
        raise TestModeRefused(409, "Seed some tickets first")
    day.closes_at = day.draw_not_before = now
    db.commit()
    close_day(db, day.id, now)
    day = test_day(db, label, lock=True)
    day.publish_not_before = day.draw_not_before + publish_gap
    db.commit()
    return day
