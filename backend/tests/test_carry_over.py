"""A real day that closes at 10 PM with fewer lucky numbers than Winners (10) is never drawn (ADR-0011):
nothing is sealed or sent to GitHub, the day becomes `carried`, and its entered cards move, still entered,
into the next day's draw. There an Admin can still Reset them, and their orders can be refunded."""

# ruff: noqa: F811 (tests take the imported `seals` fixture as their argument, the usual pytest pattern)

import sqlalchemy as sa
from test_close_and_seal import DAY, entered_numbers, seals, tick  # noqa: F401
from test_entries_api import at, enter
from test_orders_api import buy

from app.db import models as m
from app.draw.drawrun import verify_chain

TOMORROW = "2026-11-11"


def my_cards(client):
    return [c for o in client.get("/api/me/orders").json() for c in o["cards"]]


def admin_days(admin):
    return {d["label"]: d for d in admin.get("/api/admin/draw-days").json()}


def test_fewer_than_ten_at_ten_pm_moves_the_cards_to_tomorrow_and_nothing_is_sealed(
    make_client, seals, db_engine
):
    arun, admin = make_client("arun"), make_client("admin")
    at(arun, 18, 0)
    entered_numbers(arun, {"p500": 1, "p250": 2})  # 3 cards, 3 + 1 + 1 = 5 lucky numbers
    at(arun, 22, 0, 1)
    assert tick(arun)["sealed"] == []
    assert seals.files == {}  # nothing went to GitHub

    today = admin_days(admin)[DAY]
    assert (today["status"], today["ticketCount"], today["fingerprint"]) == ("carried", 0, None)
    assert today["carried"] == {"to": TOMORROW, "cards": 3, "tickets": 5}
    assert not (today["canSkip"] or today["canReset"] or today["canDelete"] or today["canRequestOtp"])
    assert admin.post(f"/api/admin/draw-days/{DAY}/otp").status_code in (404, 409)  # never drawn

    assert {(c["entered"] is not None, c["drawDay"]) for c in my_cards(arun)} == {(True, TOMORROW)}
    tomorrow = admin_days(admin)[TOMORROW]
    assert (tomorrow["status"], tomorrow["cardCount"], tomorrow["ticketCount"]) == ("open", 3, 5)

    public = {d["label"]: d for d in arun.get("/api/public/days").json()}
    assert public[DAY]["status"] == "carried" and public[DAY]["winners"] is None
    assert arun.get(f"/api/public/days/{DAY}/tickets.csv").status_code == 404
    with db_engine.connect() as conn:
        log = conn.execute(sa.select(m.DrawRun).order_by(m.DrawRun.seq)).all()
    assert [r.outcome for r in log] == ["carried-over"] and verify_chain(log)


def test_the_admin_can_reset_the_carried_cards_back_to_their_owner(make_client, seals):
    arun, admin = make_client("arun"), make_client("admin")
    at(arun, 18, 0)
    card = buy(arun, {"p500": 1})["cards"][0]
    assert arun.post(f"/api/cards/{card['id']}/scratch").status_code == 200  # scratched, then entered
    enter(arun, card["id"])
    at(arun, 22, 5)
    tick(arun)
    assert admin_days(admin)[TOMORROW]["canReset"] is True
    res = admin.post(f"/api/admin/draw-days/{TOMORROW}/reset-entries")
    assert res.status_code == 200 and (res.json()["cardCount"], res.json()["ticketCount"]) == (0, 0)
    card = my_cards(arun)[0]
    assert (card["scratched"], card["entered"], card["drawDay"]) == (True, False, None)  # in Scratched cards
    assert enter(arun, card["id"]).json()["drawDay"] == TOMORROW  # and can be entered again


def test_a_carried_order_can_be_refunded_like_any_open_entry(make_client, seals, db_engine):
    arun, admin = make_client("arun"), make_client("admin")
    at(arun, 18, 0)
    paid = buy(arun, {"p500": 1})
    enter(arun, paid["cards"][0]["id"])
    at(arun, 22, 1)
    tick(arun)
    assert admin.post(f"/api/admin/orders/{paid['id']}/refund").status_code == 200


def test_a_day_with_no_tickets_left_is_not_drawn_either(make_client, seals):
    arun, admin = make_client("arun"), make_client("admin")
    at(arun, 18, 0)
    entered_numbers(arun)  # 16
    assert admin.post(f"/api/admin/draw-days/{DAY}/reset-entries").status_code == 200  # back to 0
    at(arun, 22, 0, 1)
    tick(arun)
    assert seals.files == {}
    assert admin_days(admin)[DAY]["carried"] == {"to": TOMORROW, "cards": 0, "tickets": 0}


def test_exactly_ten_is_sealed_and_drawn_as_usual(make_client, seals):
    arun = make_client("arun")
    at(arun, 18, 0)
    entered_numbers(arun, {"p1k": 1, "p250": 2})  # 8 + 1 + 1 = 10
    at(arun, 22, 0, 1)
    assert tick(arun)["sealed"] == [DAY] and DAY in seals.files


def test_a_carried_day_carries_again_if_the_next_day_is_short_too(make_client, seals):
    arun, admin = make_client("arun"), make_client("admin")
    at(arun, 18, 0)
    entered_numbers(arun, {"p500": 1})
    at(arun, 22, 1)
    tick(arun)
    at(arun, 22, 1, day=11)
    tick(arun)
    days = admin_days(admin)
    assert days[TOMORROW]["carried"] == {"to": "2026-11-12", "cards": 1, "tickets": 3}
    assert {c["drawDay"] for c in my_cards(arun)} == {"2026-11-12"}
    assert seals.files == {}


def test_demo_draws_run_until_ten_pm(make_client, seals):
    """Skip and Delete work until 10 PM, so a presenter can run the whole flow in the evening."""
    arun, admin = make_client("arun"), make_client("admin")
    at(arun, 21, 50)
    entered_numbers(arun)  # 16
    assert admin.post(f"/api/admin/draw-days/{DAY}/skip").status_code == 200
    at(arun, 22, 0)
    assert admin.post(f"/api/admin/draw-days/{DAY}/skip").status_code == 409


def test_a_test_day_needs_ten_tickets_to_close(make_client):
    admin = make_client("admin")
    label = admin.post("/api/admin/test-days").json()["label"]
    res = admin.post(f"/api/admin/test-days/{label}/close", json={})
    assert res.status_code == 409 and "at least 10 tickets" in res.json()["detail"]
