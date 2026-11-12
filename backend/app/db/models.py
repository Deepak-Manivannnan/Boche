"""Database tables. See GLOSSARY.md for the meaning of each entity.

Portable between MySQL 8 and TiDB (ADR-0004): uniqueness and idempotency are enforced with unique
constraints, never by relying on lock behaviour or on auto-increment ID order. Money is integer paise.
"""

from datetime import UTC, date, datetime

import sqlalchemy as sa
from sqlalchemy.dialects import mysql
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship
from sqlalchemy.types import TypeDecorator

NAMING = {
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}


class UTCDateTime(TypeDecorator):
    """Stored as DATETIME(6) in UTC; always read back as an aware UTC datetime. Naive times are refused."""

    impl = sa.DateTime
    cache_ok = True

    def load_dialect_impl(self, dialect):
        return dialect.type_descriptor(mysql.DATETIME(fsp=6) if dialect.name == "mysql" else sa.DateTime())

    def process_bind_param(self, value: datetime | None, dialect):
        if value is None:
            return None
        if value.tzinfo is None:
            raise ValueError("refusing to store a naive datetime: it must carry a timezone")
        return value.astimezone(UTC).replace(tzinfo=None)

    def process_result_value(self, value: datetime | None, dialect):
        return None if value is None else value.replace(tzinfo=UTC)


LONG_BLOB = sa.LargeBinary().with_variant(mysql.LONGBLOB(), "mysql")
LONG_TEXT = sa.Text().with_variant(mysql.LONGTEXT(), "mysql")


def utcnow() -> datetime:
    return datetime.now(UTC)


class Base(DeclarativeBase):
    metadata = sa.MetaData(naming_convention=NAMING)


def enum(*values: str, name: str) -> sa.Enum:
    return sa.Enum(*values, name=name, native_enum=False, create_constraint=True, length=20)


# ------------------------------------------------------------------ people


class User(Base):
    __tablename__ = "users"
    id: Mapped[int] = mapped_column(sa.BigInteger, primary_key=True, autoincrement=True)
    # An account made with a mobile number has no Google account (or email) until it connects one.
    google_sub: Mapped[str | None] = mapped_column(sa.String(64), unique=True)
    email: Mapped[str | None] = mapped_column(sa.String(320), unique=True)
    name: Mapped[str] = mapped_column(sa.String(200))
    mobile: Mapped[str | None] = mapped_column(
        sa.String(20), unique=True
    )  # 10 digits, one account per number
    mobile_verified_at: Mapped[datetime | None] = mapped_column(UTCDateTime)
    # An Admin identity, made by signing in on the admin page with a Google email on ADMIN_EMAILS or a number
    # on ADMIN_MOBILES. Kept apart from `email` and `mobile`, so the same Google account or number can still
    # make its own customer account (which never has admin rights).
    admin_email: Mapped[str | None] = mapped_column(sa.String(320), unique=True)
    admin_mobile: Mapped[str | None] = mapped_column(sa.String(20), unique=True)
    age: Mapped[int | None] = mapped_column(sa.Integer)
    picture: Mapped[str | None] = mapped_column(
        sa.String(1000)
    )  # Google profile photo URL, set at each sign-in
    role: Mapped[str] = mapped_column(enum("customer", "admin", name="user_role"), default="customer")
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow)

    orders: Mapped[list["Order"]] = relationship(back_populates="user")


class LoginOtp(Base):
    """A one-time code sent by SMS to sign in or sign up with a mobile number. Stored salted and hashed;
    expires, allows a few wrong tries, and is used once."""

    __tablename__ = "login_otps"
    id: Mapped[int] = mapped_column(sa.BigInteger, primary_key=True, autoincrement=True)
    mobile: Mapped[str] = mapped_column(sa.String(20), index=True)
    code_hash: Mapped[str] = mapped_column(sa.String(128))
    ip: Mapped[str] = mapped_column(sa.String(64), default="")
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow, index=True)
    expires_at: Mapped[datetime] = mapped_column(UTCDateTime)
    attempts: Mapped[int] = mapped_column(sa.Integer, default=0)
    consumed_at: Mapped[datetime | None] = mapped_column(UTCDateTime)


class Address(Base):
    """A Customer's saved delivery address, visible only to that Customer. An Order keeps its own copy
    (Order.delivery), so editing or deleting a saved address never changes a past Order."""

    __tablename__ = "addresses"
    id: Mapped[int] = mapped_column(sa.BigInteger, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(sa.ForeignKey("users.id"), index=True)
    label: Mapped[str] = mapped_column(sa.String(20))  # Home, Work or Other
    name: Mapped[str] = mapped_column(sa.String(100))  # who receives the parcel
    house: Mapped[str] = mapped_column(sa.String(200))
    street: Mapped[str] = mapped_column(sa.String(200))
    pin: Mapped[str] = mapped_column(sa.String(6))
    po: Mapped[str] = mapped_column(sa.String(100), default="")
    district: Mapped[str] = mapped_column(sa.String(100))
    is_default: Mapped[bool] = mapped_column(sa.Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow)


# ------------------------------------------------------------------ buying


class Order(Base):
    __tablename__ = "orders"
    id: Mapped[int] = mapped_column(sa.BigInteger, primary_key=True, autoincrement=True)
    public_id: Mapped[str] = mapped_column(sa.String(32), unique=True)
    user_id: Mapped[int] = mapped_column(sa.ForeignKey("users.id"), index=True)
    status: Mapped[str] = mapped_column(
        enum("pending", "paid", "refunded", name="order_status"), default="pending"
    )
    subtotal_paise: Mapped[int] = mapped_column(sa.Integer)
    logistics_paise: Mapped[int] = mapped_column(sa.Integer)
    tea_gst_paise: Mapped[int] = mapped_column(sa.Integer, default=0, server_default="0")
    logistics_gst_paise: Mapped[int] = mapped_column(sa.Integer, default=0, server_default="0")
    gst_paise: Mapped[int] = mapped_column(sa.Integer)  # tea + logistics GST, rounded up to a whole rupee
    total_paise: Mapped[int] = mapped_column(sa.Integer)
    delivery: Mapped[dict | None] = mapped_column(sa.JSON)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow)
    paid_at: Mapped[datetime | None] = mapped_column(UTCDateTime)
    refunded_at: Mapped[datetime | None] = mapped_column(UTCDateTime)

    user: Mapped[User] = relationship(back_populates="orders")
    items: Mapped[list["OrderItem"]] = relationship(back_populates="order")
    cards: Mapped[list["Card"]] = relationship(back_populates="order")


class OrderItem(Base):
    __tablename__ = "order_items"
    id: Mapped[int] = mapped_column(sa.BigInteger, primary_key=True, autoincrement=True)
    order_id: Mapped[int] = mapped_column(sa.ForeignKey("orders.id"), index=True)
    pack_id: Mapped[str] = mapped_column(sa.String(16))
    qty: Mapped[int] = mapped_column(sa.Integer)
    unit_price_paise: Mapped[int] = mapped_column(sa.Integer)
    numbers_per_pack: Mapped[int] = mapped_column(sa.Integer)

    order: Mapped[Order] = relationship(back_populates="items")


class Payment(Base):
    """One confirmed payment. provider_ref is unique so a repeated confirmation is recorded once."""

    __tablename__ = "payments"
    id: Mapped[int] = mapped_column(sa.BigInteger, primary_key=True, autoincrement=True)
    order_id: Mapped[int] = mapped_column(sa.ForeignKey("orders.id"), index=True)
    provider_ref: Mapped[str] = mapped_column(sa.String(64), unique=True)
    amount_paise: Mapped[int] = mapped_column(sa.Integer)
    status: Mapped[str] = mapped_column(enum("confirmed", "refunded", name="payment_status"))
    confirmed_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow)

    order: Mapped[Order] = relationship()


class Card(Base):
    """A Scratch card: one per Pack in an Order. Entering it puts its Tickets into a Draw day."""

    __tablename__ = "cards"
    id: Mapped[int] = mapped_column(sa.BigInteger, primary_key=True, autoincrement=True)
    public_id: Mapped[str] = mapped_column(sa.String(40), unique=True)
    order_id: Mapped[int] = mapped_column(sa.ForeignKey("orders.id"), index=True)
    pack_id: Mapped[str] = mapped_column(sa.String(16))
    scratched_at: Mapped[datetime | None] = mapped_column(UTCDateTime)
    entered_at: Mapped[datetime | None] = mapped_column(UTCDateTime)
    draw_day_id: Mapped[int | None] = mapped_column(sa.ForeignKey("draw_days.id"), index=True)

    order: Mapped[Order] = relationship(back_populates="cards")
    tickets: Mapped[list["Ticket"]] = relationship(back_populates="card")
    draw_day: Mapped["DrawDay | None"] = relationship()


class Ticket(Base):
    """One lucky number. Unique across all time, so no two Draw days or cards can ever share one."""

    __tablename__ = "tickets"
    id: Mapped[int] = mapped_column(sa.BigInteger, primary_key=True, autoincrement=True)
    card_id: Mapped[int] = mapped_column(sa.ForeignKey("cards.id"), index=True)
    number: Mapped[str] = mapped_column(sa.String(16, collation="utf8mb4_bin"), unique=True)
    status: Mapped[str] = mapped_column(enum("issued", "cancelled", name="ticket_status"), default="issued")
    draw_day_id: Mapped[int | None] = mapped_column(sa.ForeignKey("draw_days.id"), index=True)
    issued_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow)
    cancelled_at: Mapped[datetime | None] = mapped_column(UTCDateTime)

    card: Mapped[Card] = relationship(back_populates="tickets")
    draw_day: Mapped["DrawDay | None"] = relationship()


# ------------------------------------------------------------------ the draw day


class DrawDay(Base):
    __tablename__ = "draw_days"
    id: Mapped[int] = mapped_column(sa.BigInteger, primary_key=True, autoincrement=True)
    label: Mapped[str] = mapped_column(sa.String(40), unique=True)  # "2026-11-10" or "test-…"
    kind: Mapped[str] = mapped_column(enum("real", "test", name="draw_day_kind"))
    day: Mapped[date] = mapped_column(sa.Date, index=True)
    status: Mapped[str] = mapped_column(enum("open", "sealed", "drawn", "published", name="draw_day_status"))
    closes_at: Mapped[datetime] = mapped_column(UTCDateTime)
    draw_not_before: Mapped[datetime] = mapped_column(UTCDateTime)
    publish_not_before: Mapped[datetime] = mapped_column(UTCDateTime)

    # Set when Entries close (the Seal)
    ticket_count: Mapped[int | None] = mapped_column(sa.Integer)
    ticket_csv: Mapped[bytes | None] = mapped_column(LONG_BLOB, deferred=True)
    fingerprint: Mapped[str | None] = mapped_column(sa.String(64))
    drand_round: Mapped[int | None] = mapped_column(sa.BigInteger)
    sealed_at: Mapped[datetime | None] = mapped_column(UTCDateTime)
    seal_json: Mapped[str | None] = mapped_column(sa.Text)
    seal_commit_sha: Mapped[str | None] = mapped_column(sa.String(64))
    seal_url: Mapped[str | None] = mapped_column(sa.String(500))

    drawn_at: Mapped[datetime | None] = mapped_column(UTCDateTime)
    published_at: Mapped[datetime | None] = mapped_column(UTCDateTime)

    result: Mapped["DrawResult | None"] = relationship(back_populates="draw_day")


class DrawResult(Base):
    __tablename__ = "draw_results"
    id: Mapped[int] = mapped_column(sa.BigInteger, primary_key=True, autoincrement=True)
    draw_day_id: Mapped[int] = mapped_column(sa.ForeignKey("draw_days.id"), unique=True)
    randomness: Mapped[str] = mapped_column(sa.String(64))
    signature: Mapped[str] = mapped_column(sa.String(256))
    seed: Mapped[str] = mapped_column(sa.String(64))
    winners: Mapped[list] = mapped_column(sa.JSON)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow)

    draw_day: Mapped[DrawDay] = relationship(back_populates="result")


class DrawRun(Base):
    """Append-only audit log of every Draw run attempt. Each entry hashes the previous one,
    so deleting or editing an entry breaks the chain. seq orders the log (not the auto-increment id)."""

    __tablename__ = "draw_runs"
    id: Mapped[int] = mapped_column(sa.BigInteger, primary_key=True, autoincrement=True)
    seq: Mapped[int] = mapped_column(sa.BigInteger, unique=True)
    draw_day_id: Mapped[int] = mapped_column(sa.ForeignKey("draw_days.id"), index=True)
    actor_user_id: Mapped[int | None] = mapped_column(sa.ForeignKey("users.id"))
    outcome: Mapped[str] = mapped_column(sa.String(30))
    detail: Mapped[str | None] = mapped_column(LONG_TEXT)
    at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow)
    prev_hash: Mapped[str] = mapped_column(sa.String(64))
    entry_hash: Mapped[str] = mapped_column(sa.String(64))

    draw_day: Mapped[DrawDay] = relationship()


class OtpChallenge(Base):
    __tablename__ = "otp_challenges"
    id: Mapped[int] = mapped_column(sa.BigInteger, primary_key=True, autoincrement=True)
    draw_day_id: Mapped[int] = mapped_column(sa.ForeignKey("draw_days.id"), index=True)
    purpose: Mapped[str] = mapped_column(sa.String(30))
    code_hash: Mapped[str] = mapped_column(sa.String(128))
    requested_by: Mapped[int] = mapped_column(sa.ForeignKey("users.id"))
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow)
    expires_at: Mapped[datetime] = mapped_column(UTCDateTime)
    attempts: Mapped[int] = mapped_column(sa.Integer, default=0)
    consumed_at: Mapped[datetime | None] = mapped_column(UTCDateTime)
    superseded_at: Mapped[datetime | None] = mapped_column(UTCDateTime)


class Claim(Base):
    __tablename__ = "claims"
    id: Mapped[int] = mapped_column(sa.BigInteger, primary_key=True, autoincrement=True)
    ticket_id: Mapped[int] = mapped_column(sa.ForeignKey("tickets.id"), unique=True)
    user_id: Mapped[int] = mapped_column(sa.ForeignKey("users.id"), index=True)
    ref: Mapped[str] = mapped_column(sa.String(32), unique=True)
    status: Mapped[str] = mapped_column(enum("submitted", "paid", name="claim_status"), default="submitted")
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow)

    ticket: Mapped[Ticket] = relationship()
    user: Mapped[User] = relationship()
