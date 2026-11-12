"""Deleting today's completed draw (ADR-0009): the Winners, Claims, sealed list and Seal are erased, the
entered cards go back to their owners, and the day reopens so it can be drawn again (Skip, or at 8:00 PM)."""

# ruff: noqa: F811 (tests take the imported `w` fixture as their argument, the usual pytest pattern)

import sqlalchemy as sa
from draw_support import DAY
from test_entries_api import at, enter
from test_orders_api import buy
from test_skip import after_round, skip, w  # noqa: F401 (w is the fixture: 16 Tickets entered at 3 PM)

from app.db import models as m
from app.draw.drawrun import verify_chain


def admin_day(w, label=DAY):
    return w.admin.get(f"/api/admin/draw-days/{label}").json()


def run_skipped_draw(w):
    day = skip(w).json()
    after_round(w, day)
    assert w.admin.post(f"/api/admin/draw-days/{DAY}/otp").status_code == 200
    res = w.admin.post(f"/api/admin/draw-days/{DAY}/run", json={"code": w.state.otp_sender.code})
    assert res.status_code == 200, res.text
    return res.json()


def delete(w, label=DAY):
    return w.admin.post(f"/api/admin/draw-days/{label}/delete")


def test_a_published_draw_today_can_be_deleted(w):
    assert run_skipped_draw(w)["canDelete"] is True


def test_deleting_erases_the_draw_and_reopens_the_day_empty(w, db_engine):
    drawn = run_skipped_draw(w)
    winning_card = next(
        c["id"]
        for o in w.arun.get("/api/me/orders").json()
        for c in o["cards"]
        if set(c["numbers"]) & {x["ticket"] for x in drawn["winners"]}
    )
    assert w.arun.post("/api/claims", json={"cardId": winning_card}).status_code == 201

    res = delete(w)
    assert res.status_code == 200, res.text
    day = res.json()
    assert (day["status"], day["ticketCount"], day["winners"], day["fingerprint"]) == ("open", 0, None, None)
    assert day["closesAt"].startswith("2026-11-10T14:30:00")  # 8:00 PM IST again
    assert DAY not in w.state.seal_publisher.files  # the Seal is gone from GitHub
    assert w.arun.get(f"/api/public/days/{DAY}/result.json").status_code == 404
    assert DAY not in [d["label"] for d in w.arun.get("/api/public/days").json()]
    with db_engine.connect() as conn:
        assert conn.scalar(sa.select(sa.func.count()).select_from(m.Claim)) == 0
        assert conn.scalar(sa.select(sa.func.count()).select_from(m.DrawResult)) == 0
        assert conn.scalar(sa.select(sa.func.count()).select_from(m.OtpChallenge)) == 0
        assert (
            conn.scalar(sa.select(sa.func.count()).select_from(m.Card).where(m.Card.entered_at.is_not(None)))
            == 0
        )
        runs = conn.execute(sa.select(m.DrawRun).order_by(m.DrawRun.seq)).all()
    assert runs[-1].outcome == "deleted" and verify_chain(runs)  # recorded, and the log is still intact


def test_after_a_delete_the_same_cards_can_be_entered_and_drawn_again(w):
    first = run_skipped_draw(w)
    delete(w)
    for o in w.arun.get("/api/me/orders").json():
        for c in o["cards"]:
            assert (c["entered"], c["drawDay"]) == (False, None)  # the card is back with its owner
            res = enter(w.arun, c["id"])
            assert res.status_code == 200, res.text
            assert res.json()["drawDay"] == DAY  # today, not tomorrow: the day is open again
    assert admin_day(w)["canSkip"] is True
    second = run_skipped_draw(w)
    assert second["status"] == "published" and second["ticketCount"] == 16
    assert second["drandRound"] > first["drandRound"]  # a new Seal with a new Randomness round
    assert DAY in w.state.seal_publisher.files


def test_a_draw_that_has_not_run_cannot_be_deleted(w):
    assert delete(w).status_code == 409  # open
    skip(w)
    res = delete(w)  # sealed, not drawn
    assert res.status_code == 409 and "not been run" in res.json()["detail"]


def test_no_delete_after_8pm(w):
    run_skipped_draw(w)
    at(w.admin, 20, 0)
    assert admin_day(w)["canDelete"] is False
    res = delete(w)
    assert res.status_code == 409 and "before 8:00 PM" in res.json()["detail"]
    assert admin_day(w)["status"] == "published"


def test_yesterdays_draw_cannot_be_deleted(w):
    run_skipped_draw(w)
    at(w.admin, 10, 0, day=11)
    assert delete(w).status_code == 409


def test_a_github_failure_deletes_nothing(w):
    run_skipped_draw(w)
    w.state.seal_publisher.fail_next = 1
    res = delete(w)
    assert res.status_code == 502
    day = admin_day(w)
    assert day["status"] == "published" and len(day["winners"]) == 10
    assert DAY in w.state.seal_publisher.files


def test_test_days_are_not_deleted_this_way(w):
    label = w.admin.post("/api/admin/test-days").json()["label"]
    assert delete(w, label).status_code == 409


def test_only_an_admin_can_delete(w):
    run_skipped_draw(w)
    assert w.arun.post(f"/api/admin/draw-days/{DAY}/delete").status_code == 403
    assert admin_day(w)["status"] == "published"


def test_new_cards_after_a_delete_go_into_today(w):
    run_skipped_draw(w)
    delete(w)
    card = buy(w.arun, {"p250": 1})["cards"][0]
    assert enter(w.arun, card["id"]).json()["drawDay"] == DAY
