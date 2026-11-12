"""Skip (ADR-0008): an Admin closes today's real Draw day early, so the Founder's OTP and the draw run
straight away instead of waiting for 8:00 / 8:15 PM. The list is still sealed before its randomness exists."""

import json
from datetime import datetime, timedelta
from types import SimpleNamespace

import pytest
from draw_support import DAY, FakeDrand, FakeOtp, drand_value
from test_close_and_seal import FakeSeals
from test_entries_api import at, enter
from test_orders_api import buy

import verify
from app.draw.drand import round_released_at

TOMORROW = "2026-11-11"


@pytest.fixture
def w(make_client):
    arun, admin = make_client("arun"), make_client("admin")
    state = admin.app.state
    state.otp_sender, state.drand_fetch, state.seal_publisher = FakeOtp(), FakeDrand(), FakeSeals()
    at(arun, 15, 0)
    order = buy(arun, {"p1k": 2})  # 16 Tickets: a draw needs at least 10
    for card in order["cards"]:
        assert enter(arun, card["id"]).status_code == 200
    return SimpleNamespace(arun=arun, admin=admin, state=state, order_id=order["id"])


def admin_day(w, label=DAY):
    return w.admin.get(f"/api/admin/draw-days/{label}").json()


def skip(w, label=DAY):
    return w.admin.post(f"/api/admin/draw-days/{label}/skip")


def after_round(w, day):
    w.state.test_clock.set(datetime.fromisoformat(day["roundReleasedAt"]) + timedelta(seconds=1))


def test_an_open_real_day_with_tickets_can_be_skipped(w):
    assert admin_day(w)["canSkip"] is True


def test_skip_seals_now_with_a_round_still_in_the_future(w):
    now = w.state.test_clock.now()
    res = skip(w)
    assert res.status_code == 200, res.text
    day = res.json()
    assert (day["status"], day["kind"], day["ticketCount"], day["canSkip"]) == ("sealed", "real", 16, False)
    assert datetime.fromisoformat(day["sealedAt"]) == now
    released = round_released_at(day["drandRound"])
    assert released >= now + timedelta(seconds=30)  # the list is fixed before its randomness exists
    assert datetime.fromisoformat(day["drawNotBefore"]) == released
    assert day["publishNotBefore"] == day["drawNotBefore"]  # published straight after the draw
    assert day["sealPublished"] is True
    assert DAY in w.state.seal_publisher.files


def test_after_a_skip_the_otp_waits_for_the_round_then_the_draw_publishes_at_once(w, tmp_path):
    day = skip(w).json()
    assert day["canRequestOtp"] is False
    assert w.admin.post(f"/api/admin/draw-days/{DAY}/otp").status_code == 409

    after_round(w, day)
    assert admin_day(w)["canRequestOtp"] is True
    assert w.admin.post(f"/api/admin/draw-days/{DAY}/otp").status_code == 200
    run = w.admin.post(f"/api/admin/draw-days/{DAY}/run", json={"code": w.state.otp_sender.code})
    assert run.status_code == 200, run.text
    assert run.json()["status"] == "published"  # well before 8:30 PM

    for name in ("tickets.csv", "seal.json", "result.json"):
        (tmp_path / name).write_bytes(w.admin.get(f"/api/public/days/{DAY}/{name}").content)
    seal = json.loads((tmp_path / "seal.json").read_text())
    (tmp_path / "drand.json").write_text(json.dumps(drand_value(seal["drand"]["round"])))
    report = verify.verify(DAY, verify.FolderSources(tmp_path))
    assert report.ok, report.render()


def test_cards_entered_after_a_skip_go_into_tomorrows_draw(w):
    skip(w)
    card = buy(w.arun, {"p250": 1})["cards"][0]
    res = enter(w.arun, card["id"])
    assert res.status_code == 200, res.text
    assert res.json()["drawDay"] == TOMORROW
    assert admin_day(w)["ticketCount"] == 16  # today's sealed list is unchanged


def test_tomorrows_day_cannot_be_skipped_today(w):
    skip(w)
    enter(w.arun, buy(w.arun, {"p250": 1})["cards"][0]["id"])
    assert admin_day(w, TOMORROW)["canSkip"] is False
    res = skip(w, TOMORROW)
    assert res.status_code == 409 and "today" in res.json()["detail"]


def test_a_day_can_only_be_skipped_once(w):
    assert skip(w).status_code == 200
    res = skip(w)
    assert res.status_code == 409 and "already closed" in res.json()["detail"]


def test_a_day_already_sealed_at_8pm_cannot_be_skipped(w):
    at(w.arun, 20, 0, 1)
    w.arun.post("/api/tick")
    assert admin_day(w)["status"] == "sealed"
    assert skip(w).status_code == 409


def test_a_day_with_fewer_tickets_than_winners_cannot_be_skipped(w):
    """Sealed with under 10 Tickets, the draw could never run, so Skip refuses rather than strand the day."""
    assert w.admin.post(f"/api/admin/orders/{w.order_id}/refund").status_code == 200  # the day's only order
    for card in buy(w.arun, {"p1k": 1, "p250": 1})["cards"]:  # 9 Tickets
        assert enter(w.arun, card["id"]).status_code == 200
    assert admin_day(w)["ticketCount"] == 9
    assert admin_day(w)["canSkip"] is False
    res = skip(w)
    assert res.status_code == 409 and "at least 10" in res.json()["detail"]
    assert admin_day(w)["status"] == "open"


def test_test_days_are_not_skipped(w):
    label = w.admin.post("/api/admin/test-days").json()["label"]
    assert admin_day(w, label)["canSkip"] is False
    assert skip(w, label).status_code == 409


def test_only_an_admin_can_skip(w):
    assert w.arun.post(f"/api/admin/draw-days/{DAY}/skip").status_code == 403
    assert admin_day(w)["status"] == "open"


def test_an_unknown_day_is_404(w):
    assert skip(w, "2026-01-01").status_code == 404
