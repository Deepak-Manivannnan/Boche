"""Schema behaviour on a real MySQL test database, built by running the Alembic migrations."""

from datetime import UTC, date, datetime

import pytest
import sqlalchemy as sa
from sqlalchemy.exc import IntegrityError

from app.db import models as m

EXPECTED_TABLES = {
    "users",
    "orders",
    "order_items",
    "payments",
    "cards",
    "tickets",
    "draw_days",
    "draw_results",
    "draw_runs",
    "otp_challenges",
    "claims",
    "addresses",
}


def make_order(session, email="a@example.com") -> m.Order:
    user = m.User(google_sub=f"sub-{email}", email=email, name="Arun Mathew")
    order = m.Order(
        public_id=f"TEA-{abs(hash(email)) % 10**6:06d}",
        user=user,
        status="paid",
        subtotal_paise=32000,
        logistics_paise=5200,
        gst_paise=2536,
        total_paise=39736,
    )
    session.add(order)
    session.flush()
    return order


def make_card(session, order, n=1) -> m.Card:
    card = m.Card(public_id=f"{order.public_id}-{n}", order=order, pack_id="p1k")
    session.add(card)
    session.flush()
    return card


def make_day(session, label="2026-11-10", kind="real") -> m.DrawDay:
    day = m.DrawDay(
        label=label,
        kind=kind,
        day=date(2026, 11, 10),
        status="open",
        closes_at=datetime(2026, 11, 10, 14, 30, tzinfo=UTC),
        draw_not_before=datetime(2026, 11, 10, 14, 45, tzinfo=UTC),
        publish_not_before=datetime(2026, 11, 10, 15, 0, tzinfo=UTC),
    )
    session.add(day)
    session.flush()
    return day


def test_migrations_create_every_table(db_engine):
    assert EXPECTED_TABLES <= set(sa.inspect(db_engine).get_table_names())


def test_the_migrations_match_the_models_exactly(migrated_url):
    from alembic import command

    from app.core.migrate import _config

    command.check(_config(migrated_url))  # raises if a model change has no migration


def test_migrations_can_be_rolled_back_and_reapplied(migrated_url):
    from app.core.migrate import downgrade_all, upgrade_to_head

    downgrade_all(migrated_url)
    assert not EXPECTED_TABLES & set(sa.inspect(sa.create_engine(migrated_url)).get_table_names())
    upgrade_to_head(migrated_url)
    assert EXPECTED_TABLES <= set(sa.inspect(sa.create_engine(migrated_url)).get_table_names())


def test_a_lucky_number_can_never_be_issued_twice(session):
    order = make_order(session)
    first, second = make_card(session, order, 1), make_card(session, order, 2)
    session.add_all([m.Ticket(card=first, number="AB 123456"), m.Ticket(card=second, number="AB 123456")])
    with pytest.raises(IntegrityError):
        session.flush()


def test_lucky_numbers_differing_only_in_case_are_different_tickets(session):
    order = make_order(session)
    card = make_card(session, order)
    session.add_all([m.Ticket(card=card, number="AB 000001"), m.Ticket(card=card, number="ab 000001")])
    session.flush()  # utf8mb4_bin: exact comparison, so no clash


def test_a_draw_day_label_is_unique(session):
    make_day(session, "2026-11-10")
    with pytest.raises(IntegrityError):
        make_day(session, "2026-11-10")


def test_a_draw_day_has_at_most_one_result(session):
    day = make_day(session)
    session.add(
        m.DrawResult(draw_day=day, randomness="aa" * 32, signature="bb" * 48, seed="cc" * 32, winners=[])
    )
    session.flush()
    session.add(
        m.DrawResult(draw_day=day, randomness="aa" * 32, signature="bb" * 48, seed="cc" * 32, winners=[])
    )
    with pytest.raises(IntegrityError):
        session.flush()


def test_a_payment_confirmation_is_recorded_only_once(session):
    order = make_order(session)
    session.add(m.Payment(order=order, provider_ref="mockpay_1", amount_paise=39736, status="confirmed"))
    session.flush()
    session.add(m.Payment(order=order, provider_ref="mockpay_1", amount_paise=39736, status="confirmed"))
    with pytest.raises(IntegrityError):
        session.flush()


def test_a_ticket_can_be_claimed_only_once(session):
    order = make_order(session)
    ticket = m.Ticket(card=make_card(session, order), number="CD 654321")
    session.add(ticket)
    session.flush()
    session.add(m.Claim(ticket=ticket, user=order.user, ref="CLM-000001"))
    session.flush()
    session.add(m.Claim(ticket=ticket, user=order.user, ref="CLM-000002"))
    with pytest.raises(IntegrityError):
        session.flush()


def test_draw_run_log_positions_are_unique(session):
    day = make_day(session)
    session.add(m.DrawRun(seq=1, draw_day=day, outcome="completed", prev_hash="0" * 64, entry_hash="1" * 64))
    session.flush()
    session.add(m.DrawRun(seq=1, draw_day=day, outcome="completed", prev_hash="0" * 64, entry_hash="2" * 64))
    with pytest.raises(IntegrityError):
        session.flush()


def test_times_are_stored_and_read_back_as_aware_utc(session):
    day = make_day(session)
    session.expire_all()
    loaded = session.get(m.DrawDay, day.id)
    assert loaded.closes_at == datetime(2026, 11, 10, 14, 30, tzinfo=UTC)
    assert loaded.closes_at.tzinfo is not None


def test_a_naive_time_is_refused_rather_than_guessed(session):
    day = make_day(session)
    day.sealed_at = datetime(2026, 11, 10, 20, 0)
    with pytest.raises(Exception, match="timezone"):
        session.flush()


def test_the_sealed_ticket_list_is_stored_byte_for_byte(session):
    day = make_day(session)
    csv = b"position,ticket_number\n" + b"".join(f"{i},AB {i:06d}\n".encode() for i in range(1, 100_001))
    day.ticket_csv = csv
    session.flush()
    session.expire_all()
    assert session.get(m.DrawDay, day.id).ticket_csv == csv
