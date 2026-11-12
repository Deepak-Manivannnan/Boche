"""Entering the draw and refunds. The server's IST clock decides the Draw day, never the phone's."""

from datetime import UTC, datetime

import pytest
import sqlalchemy as sa
from test_orders_api import buy

from app.db import models as m

DAY = "2026-11-10"
NEXT_DAY = "2026-11-11"


def at(client, hh, mm, ss=0, day=10):
    """Set the server clock to an IST wall-clock time on 2026-11-<day>."""
    from app.core.clock import IST

    client.app.state.test_clock.set(datetime(2026, 11, day, hh, mm, ss, tzinfo=IST))


def enter(client, card_id):
    return client.post("/api/draw/entries", json={"cardId": card_id})


def first_card(client, items=None):
    return buy(client, items or {"p500": 1})["cards"][0]


def ticket_rows(db_engine):
    with db_engine.connect() as conn:
        rows = conn.execute(
            sa.select(m.Ticket.number, m.Ticket.status, m.DrawDay.label).join(
                m.DrawDay, m.Ticket.draw_day_id == m.DrawDay.id, isouter=True
            )
        ).all()
    return {number: (status, label) for number, status, label in rows}


# ---------------------------------------------------------------- which Draw day


def test_an_entry_before_ten_pm_ist_goes_into_todays_draw(make_client, db_engine):
    client = make_client()
    card = first_card(client)
    at(client, 21, 59, 59)
    res = enter(client, card["id"])
    assert res.status_code == 200, res.text
    assert res.json()["drawDay"] == DAY
    assert {label for _, label in ticket_rows(db_engine).values()} == {DAY}


def test_an_entry_at_ten_pm_ist_goes_into_tomorrows_draw(make_client):
    client = make_client()
    card = first_card(client)
    at(client, 22, 0, 0)
    assert enter(client, card["id"]).json()["drawDay"] == NEXT_DAY


def test_after_midnight_ist_an_entry_goes_into_that_new_days_draw(make_client):
    client = make_client()
    card = first_card(client)
    at(client, 0, 30, day=11)  # 00:30 IST on the 11th is still the 10th in UTC
    assert enter(client, card["id"]).json()["drawDay"] == NEXT_DAY


def test_the_draw_day_carries_its_ist_schedule(make_client, db_engine):
    client = make_client()
    at(client, 12, 0)
    enter(client, first_card(client)["id"])
    with db_engine.connect() as conn:
        day = conn.execute(sa.select(m.DrawDay).where(m.DrawDay.label == DAY)).one()
    assert (day.kind, day.status) == ("real", "open")
    assert day.closes_at.replace(tzinfo=None) == datetime(2026, 11, 10, 16, 30)
    assert day.draw_not_before.replace(tzinfo=None) == datetime(2026, 11, 10, 16, 45)
    assert day.publish_not_before.replace(tzinfo=None) == datetime(2026, 11, 10, 17, 0)


def test_a_draw_day_closed_early_sends_new_entries_to_tomorrow(make_client, db_engine):
    """Once today's list closes before 10 PM (an Admin's Skip), it never changes; new cards go to tomorrow."""
    client = make_client()
    at(client, 12, 0)
    enter(client, first_card(client)["id"])
    with db_engine.begin() as conn:
        conn.execute(sa.update(m.DrawDay).where(m.DrawDay.label == DAY).values(status="sealed"))
    res = enter(client, first_card(client)["id"])
    assert res.status_code == 200, res.text
    assert res.json()["drawDay"] == "2026-11-11"
    with db_engine.connect() as conn:
        today = conn.scalar(sa.select(m.DrawDay.id).where(m.DrawDay.label == DAY))
        cards = sa.select(sa.func.count()).select_from(m.Card).where(m.Card.draw_day_id == today)
        assert conn.scalar(cards) == 1


# ---------------------------------------------------------------- who and how often


def test_entering_the_same_card_twice_changes_nothing(make_client):
    client = make_client()
    card, other = buy(client, {"p1k": 2})["cards"]  # 16 lucky numbers: enough for the day to be drawn
    at(client, 12, 0)
    first = enter(client, card["id"]).json()
    enter(client, other["id"])
    at(client, 22, 30)  # even after the cut-off, the card stays in the day it was entered into
    again = enter(client, card["id"])
    assert again.status_code == 200
    assert again.json() == first


def test_a_customer_cannot_enter_someone_elses_card(make_client, db_engine):
    arun, meera = make_client("arun"), make_client("meera")
    card = first_card(arun)
    assert enter(meera, card["id"]).status_code == 404
    assert {label for _, label in ticket_rows(db_engine).values()} == {None}


def test_entering_needs_a_signed_in_customer(make_client):
    assert enter(make_client(None), "TEA-XXXX-1").status_code == 401


def test_my_orders_shows_which_draw_day_each_card_is_in(make_client):
    client = make_client()
    paid = buy(client, {"p250": 2})
    at(client, 12, 0)
    enter(client, paid["cards"][0]["id"])
    cards = client.get("/api/me/orders").json()[0]["cards"]
    assert [(c["entered"], c["drawDay"]) for c in cards] == [(True, DAY), (False, None)]


# ---------------------------------------------------------------- refunds


def refund(admin, order_id):
    return admin.post(f"/api/admin/orders/{order_id}/refund")


def test_a_refund_before_entries_close_cancels_the_tickets(make_client, db_engine):
    arun, admin = make_client("arun"), make_client("admin")
    paid = buy(arun, {"p500": 1})
    at(arun, 15, 0)
    enter(arun, paid["cards"][0]["id"])
    res = refund(admin, paid["id"])
    assert res.status_code == 200, res.text
    assert res.json()["status"] == "refunded"
    assert {status for status, _ in ticket_rows(db_engine).values()} == {"cancelled"}
    assert arun.get("/api/me/orders").json()[0]["status"] == "refunded"


def test_a_refunded_card_cannot_be_entered(make_client):
    arun, admin = make_client("arun"), make_client("admin")
    paid = buy(arun, {"p500": 1})
    refund(admin, paid["id"])
    assert enter(arun, paid["cards"][0]["id"]).status_code == 409


def test_after_entries_close_a_refund_waits_for_the_results(make_client, db_engine):
    arun, admin = make_client("arun"), make_client("admin")
    paid = buy(arun, {"p1k": 2})  # 16 lucky numbers: the day is sealed and drawn
    at(arun, 21, 0)
    for card in paid["cards"]:
        enter(arun, card["id"])
    at(arun, 22, 0)
    assert refund(admin, paid["id"]).status_code == 409
    assert {status for status, _ in ticket_rows(db_engine).values()} == {"issued"}


def test_a_refund_is_allowed_again_once_results_are_published(make_client, db_engine):
    arun, admin = make_client("arun"), make_client("admin")
    paid = buy(arun, {"p500": 1})
    at(arun, 21, 0)
    enter(arun, paid["cards"][0]["id"])
    with db_engine.begin() as conn:
        conn.execute(sa.update(m.DrawDay).where(m.DrawDay.label == DAY).values(status="published"))
    at(arun, 23, 0)
    assert refund(admin, paid["id"]).status_code == 200


def test_an_order_holding_a_winning_ticket_can_never_be_refunded(make_client, db_engine):
    arun, admin = make_client("arun"), make_client("admin")
    paid = buy(arun, {"p500": 1})
    at(arun, 21, 0)
    enter(arun, paid["cards"][0]["id"])
    winner = paid["cards"][0]["numbers"][1]
    with db_engine.begin() as conn:
        day_id = conn.scalar(sa.select(m.DrawDay.id).where(m.DrawDay.label == DAY))
        conn.execute(sa.update(m.DrawDay).where(m.DrawDay.id == day_id).values(status="published"))
        conn.execute(
            sa.insert(m.DrawResult).values(
                draw_day_id=day_id,
                randomness="aa" * 32,
                signature="bb" * 48,
                seed="cc" * 32,
                winners=[{"rank": 4, "prize": "consolation", "position": 1, "ticket": winner}],
                created_at=datetime(2026, 11, 10, 16, 46, tzinfo=UTC),
            )
        )
    at(arun, 23, 0)
    assert refund(admin, paid["id"]).status_code == 409


def test_an_unentered_order_can_be_refunded_any_time(make_client, db_engine):
    arun, admin = make_client("arun"), make_client("admin")
    paid = buy(arun, {"p250": 1})
    at(arun, 22, 45)
    assert refund(admin, paid["id"]).status_code == 200
    assert {status for status, _ in ticket_rows(db_engine).values()} == {"cancelled"}


def test_refunding_twice_is_refused(make_client):
    arun, admin = make_client("arun"), make_client("admin")
    paid = buy(arun, {"p250": 1})
    refund(admin, paid["id"])
    assert refund(admin, paid["id"]).status_code == 409


@pytest.mark.parametrize("who", ["arun", None])
def test_only_an_admin_can_refund(make_client, who):
    arun = make_client("arun")
    paid = buy(arun, {"p250": 1})
    caller = arun if who else make_client(None)
    assert refund(caller, paid["id"]).status_code == (403 if who else 401)
