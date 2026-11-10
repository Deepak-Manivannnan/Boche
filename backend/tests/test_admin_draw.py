"""Ticket 09: an Admin enters the Founder's OTP and the draw runs exactly once, using only sealed inputs."""

import re
from dataclasses import replace
from types import SimpleNamespace

import pytest
import sqlalchemy as sa
from draw_support import drand_value, sealed_day
from test_entries_api import at

from app import models as m
from app.drawrun import verify_chain
from engine import pick_winners

DAY = "2026-11-10"
BASE = f"/api/admin/draw-days/{DAY}"


@pytest.fixture
def w(make_client):
    return sealed_day(make_client)


def ask_otp(w):
    return w.admin.post(f"{BASE}/otp")


def run(w, code):
    return w.admin.post(f"{BASE}/run", json={"code": code})


def ready(w):
    """8:15:05 PM IST: the sealed Randomness round has been released."""
    at(w.admin, 20, 15, 5)


def expected_winners(w):
    round_no = w.admin.get(BASE).json()["drandRound"]
    result = pick_winners(w.numbers, drand_value(round_no)["randomness"], DAY)
    return [[x.rank, x.prize, x.position, x.ticket] for x in result.winners]


def as_rows(winners):
    return [[x["rank"], x["prize"], x["position"], x["ticket"]] for x in winners]


# ---------------------------------------------------------------- who may act


def test_only_admins_can_see_or_act_on_draw_days(w):
    for method, path in (("get", "/api/admin/draw-days"), ("get", BASE), ("post", f"{BASE}/otp")):
        assert getattr(w.arun, method)(path).status_code == 403
    assert run(SimpleNamespace(admin=w.arun), "123456").status_code == 403


def test_an_admin_removed_from_the_list_loses_access_immediately(w):
    w.state.settings = replace(w.state.settings, admin_emails=frozenset())
    assert w.admin.get("/api/admin/draw-days").status_code == 403


def test_the_admin_api_offers_no_way_to_redraw_edit_or_reject_winners(w):
    paths = w.admin.get("/openapi.json").json()["paths"]
    admin_routes = {(p, tuple(sorted(k.upper() for k in ops))) for p, ops in paths.items() if "/admin/" in p}
    assert admin_routes == {
        ("/api/admin/draw-days", ("GET",)),
        ("/api/admin/draw-days/{label}", ("GET",)),
        ("/api/admin/draw-days/{label}/otp", ("POST",)),
        ("/api/admin/draw-days/{label}/run", ("POST",)),
        ("/api/admin/orders/{order_id}/refund", ("POST",)),
    }


# ---------------------------------------------------------------- requesting the OTP


def test_no_otp_before_the_randomness_round_is_released(w):
    at(w.admin, 20, 10)
    assert ask_otp(w).status_code == 409
    assert w.state.otp_sender.sent == []


def test_no_otp_for_a_day_that_has_not_closed(w):
    at(w.admin, 19, 0, day=11)
    assert w.admin.post("/api/admin/draw-days/2026-11-11/otp").status_code == 404


def test_the_founder_gets_an_otp_naming_the_day_ticket_count_and_fingerprint(w):
    ready(w)
    res = ask_otp(w)
    assert res.status_code == 200, res.text
    assert "code" not in res.json() and w.state.otp_sender.code not in res.text
    to, text = w.state.otp_sender.sent[0]
    fp = w.admin.get(BASE).json()["fingerprint"]
    assert to == "+919800000000"
    assert DAY in text and "16 tickets" in text and fp[:12] in text
    assert re.fullmatch(r"\d{6}", w.state.otp_sender.code)


def test_a_second_otp_request_within_a_minute_is_refused(w):
    ready(w)
    ask_otp(w)
    at(w.admin, 20, 15, 30)
    assert ask_otp(w).status_code == 429
    assert len(w.state.otp_sender.sent) == 1


def test_a_new_otp_replaces_the_old_one(w):
    ready(w)
    ask_otp(w)
    old = w.state.otp_sender.code
    at(w.admin, 20, 16, 10)
    ask_otp(w)
    new = w.state.otp_sender.code
    if old != new:
        assert run(w, old).status_code == 401
    assert run(w, new).status_code == 200


# ---------------------------------------------------------------- entering the OTP


def test_the_draw_cannot_run_without_an_otp_being_requested(w):
    ready(w)
    assert run(w, "123456").status_code == 409


def test_a_wrong_otp_does_not_run_the_draw(w):
    ready(w)
    ask_otp(w)
    wrong = "000000" if w.state.otp_sender.code != "000000" else "111111"
    res = run(w, wrong)
    assert res.status_code == 401
    assert "4 tries left" in res.json()["detail"]
    assert w.admin.get(BASE).json()["status"] == "sealed"


def test_five_wrong_otps_lock_that_code(w):
    ready(w)
    ask_otp(w)
    good = w.state.otp_sender.code
    wrong = "000000" if good != "000000" else "111111"
    for _ in range(5):
        run(w, wrong)
    assert run(w, good).status_code == 429


def test_an_otp_expires_after_five_minutes(w):
    ready(w)
    ask_otp(w)
    at(w.admin, 20, 20, 6)
    assert run(w, w.state.otp_sender.code).status_code == 401


@pytest.mark.parametrize("bad", ["12345", "1234567", "abcdef", ""])
def test_a_malformed_otp_is_rejected_without_counting(w, bad):
    ready(w)
    ask_otp(w)
    assert run(w, bad).status_code == 422
    assert run(w, w.state.otp_sender.code).status_code == 200


# ---------------------------------------------------------------- the draw run


def test_the_right_otp_runs_the_draw_on_the_sealed_list_and_drand_round(w):
    ready(w)
    ask_otp(w)
    res = run(w, w.state.otp_sender.code)
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["status"] == "drawn"
    assert as_rows(body["winners"]) == expected_winners(w)
    assert [x["prize"] for x in body["winners"]] == ["main"] * 3 + ["consolation"] * 7


def test_running_again_returns_the_saved_result_and_never_draws_twice(w, db_engine):
    ready(w)
    ask_otp(w)
    code = w.state.otp_sender.code
    first = run(w, code).json()
    at(w.admin, 20, 40)
    again = run(w, "999999")
    assert again.status_code == 200
    assert again.json()["winners"] == first["winners"]
    assert ask_otp(w).status_code == 409  # nothing left to approve
    with db_engine.connect() as conn:
        assert conn.scalar(sa.select(sa.func.count()).select_from(m.DrawResult)) == 1


def test_a_crash_mid_draw_saves_nothing_and_a_retry_gives_the_same_winners(w, monkeypatch):
    import app.drawrun as drawrun

    real, calls = drawrun.pick_winners, []

    def crash_once(*args, **kwargs):
        calls.append(1)
        if len(calls) == 1:
            raise RuntimeError("server crashed mid-draw")
        return real(*args, **kwargs)

    monkeypatch.setattr(drawrun, "pick_winners", crash_once)
    ready(w)
    ask_otp(w)
    code = w.state.otp_sender.code
    assert run(w, code).status_code == 500
    assert w.admin.get(BASE).json()["status"] == "sealed"
    retry = run(w, code)
    assert retry.status_code == 200
    assert as_rows(retry.json()["winners"]) == expected_winners(w)


def test_if_drand_is_unreachable_the_draw_waits_and_the_otp_stays_valid(w):
    ready(w)
    ask_otp(w)
    w.state.drand_fetch.down = True
    assert run(w, w.state.otp_sender.code).status_code == 503
    w.state.drand_fetch.down = False
    assert run(w, w.state.otp_sender.code).status_code == 200


def test_every_run_attempt_is_logged_in_a_hash_chain(w, db_engine):
    ready(w)
    ask_otp(w)
    w.state.drand_fetch.down = True
    run(w, w.state.otp_sender.code)
    w.state.drand_fetch.down = False
    run(w, w.state.otp_sender.code)
    run(w, "000000")
    with db_engine.connect() as conn:
        rows = conn.execute(sa.select(m.DrawRun).order_by(m.DrawRun.seq)).all()
    assert [r.outcome for r in rows] == ["failed", "completed", "repeat"]
    assert rows[0].prev_hash == "0" * 64
    assert verify_chain(rows)
    tampered = [SimpleNamespace(**r._mapping) for r in rows]
    tampered[0].detail = tampered[0].detail.replace("relays unreachable", "all fine")
    assert not verify_chain(tampered)


def test_the_draw_days_list_shows_status_and_winners(w):
    ready(w)
    days = w.admin.get("/api/admin/draw-days").json()
    assert [(d["label"], d["status"], d["ticketCount"], d["canRequestOtp"]) for d in days] == [
        (DAY, "sealed", 16, True)
    ]
    ask_otp(w)
    run(w, w.state.otp_sender.code)
    day = w.admin.get("/api/admin/draw-days").json()[0]
    assert day["status"] == "drawn" and len(day["winners"]) == 10 and day["canRequestOtp"] is False
