"""Reset entries: while a real day still takes entries, an Admin gives every entered card back to its owner
(scratched, not entered) so the same cards can be entered again. For repeated demos; nothing is drawn."""

# ruff: noqa: F811 (tests take the imported `w` fixture as their argument, the usual pytest pattern)

import sqlalchemy as sa
from draw_support import DAY
from test_entries_api import at, enter
from test_skip import after_round, skip, w  # noqa: F401 (w: 2 cards, 16 lucky numbers entered at 3 PM)

from app.db import models as m
from app.draw.drawrun import verify_chain


def admin_day(w, label=DAY):
    return w.admin.get(f"/api/admin/draw-days/{label}").json()


def reset(w, label=DAY):
    return w.admin.post(f"/api/admin/draw-days/{label}/reset-entries")


def my_cards(w):
    return [c for o in w.arun.get("/api/me/orders").json() for c in o["cards"]]


def test_an_open_day_with_entries_can_be_reset(w):
    assert admin_day(w)["canReset"] is True


def test_reset_gives_every_entered_card_back_and_the_counts_go_to_zero(w, db_engine):
    before = my_cards(w)
    assert all(c["entered"] for c in before)
    assert w.arun.post(f"/api/cards/{before[0]['id']}/scratch").status_code == 200  # one scratched, one not
    res = reset(w)
    assert res.status_code == 200, res.text
    day = res.json()
    assert (day["status"], day["ticketCount"], day["cardCount"], day["canReset"]) == ("open", 0, 0, False)
    after = my_cards(w)
    assert [(c["id"], c["numbers"]) for c in after] == [
        (c["id"], c["numbers"]) for c in before
    ]  # still theirs
    assert all(not c["entered"] and c["drawDay"] is None for c in after)  # out of the draw, ready to enter
    # Scratched stays as it was: the scratched card waits under Scratched cards, the other under Unscratched
    assert [c["scratched"] for c in after] == [True, False]
    with db_engine.connect() as conn:
        runs = conn.execute(sa.select(m.DrawRun).order_by(m.DrawRun.seq)).all()
    assert runs[-1].outcome == "entries-reset" and '"tickets":16' in runs[-1].detail and verify_chain(runs)


def test_after_a_reset_the_same_cards_go_in_again_and_the_draw_runs(w):
    reset(w)
    for c in my_cards(w):
        res = enter(w.arun, c["id"])
        assert res.status_code == 200 and res.json()["drawDay"] == DAY
    assert (admin_day(w)["ticketCount"], admin_day(w)["cardCount"]) == (16, 2)
    day = skip(w).json()
    after_round(w, day)
    assert w.admin.post(f"/api/admin/draw-days/{DAY}/otp").status_code == 200
    run = w.admin.post(f"/api/admin/draw-days/{DAY}/run", json={"code": w.state.otp_sender.code})
    assert run.status_code == 200 and run.json()["status"] == "published"


def test_not_once_entries_have_closed(w):
    skip(w)
    assert admin_day(w)["canReset"] is False
    res = reset(w)
    assert res.status_code == 409 and "closed" in res.json()["detail"]
    assert admin_day(w)["ticketCount"] == 16  # the sealed list is untouched


def test_not_after_8pm(w):
    at(w.arun, 20, 0, 1)
    w.arun.post("/api/tick")
    assert reset(w).status_code == 409


def test_nothing_to_reset(w):
    reset(w)
    res = reset(w)
    assert res.status_code == 409 and "No cards" in res.json()["detail"]


def test_not_for_test_days(w):
    label = w.admin.post("/api/admin/test-days").json()["label"]
    assert admin_day(w, label)["canReset"] is False
    assert reset(w, label).status_code == 409


def test_only_an_admin_can_reset(w):
    assert w.arun.post(f"/api/admin/draw-days/{DAY}/reset-entries").status_code == 403
    assert admin_day(w)["ticketCount"] == 16
