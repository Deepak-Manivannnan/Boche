"""Ticket 12: an Admin runs a whole Draw day on demand. Test days use the same code paths as real days
(paid Orders, Seal, Founder OTP, draw, publish) and never touch a real Draw day."""

import json
from types import SimpleNamespace

import pytest
import sqlalchemy as sa
from draw_support import FakeDrand, FakeOtp, drand_value
from test_close_and_seal import FakeSeals
from test_entries_api import at, enter
from test_orders_api import buy

import verify
from app.db import models as m
from app.draw.drand import round_released_at


@pytest.fixture
def t(make_client):
    arun, admin = make_client("arun"), make_client("admin")
    state = admin.app.state
    state.otp_sender, state.drand_fetch, state.seal_publisher = FakeOtp(), FakeDrand(), FakeSeals()
    at(admin, 15, 0)
    return SimpleNamespace(arun=arun, admin=admin, state=state)


def new_day(t):
    res = t.admin.post("/api/admin/test-days")
    assert res.status_code == 201, res.text
    return res.json()["label"]


def seed(t, label, count):
    res = t.admin.post(f"/api/admin/test-days/{label}/seed", json={"count": count})
    assert res.status_code == 200, res.text
    return res.json()


def close(t, label, gap=0):
    res = t.admin.post(f"/api/admin/test-days/{label}/close", json={"publishGapMinutes": gap})
    assert res.status_code == 200, res.text
    return res.json()


def after_round(t, day):
    """Move the clock to just after the sealed Randomness round is released."""
    from datetime import datetime, timedelta

    t.state.test_clock.set(datetime.fromisoformat(day["roundReleasedAt"]) + timedelta(seconds=1))


def ticket_count(db_engine, label):
    with db_engine.connect() as conn:
        return conn.scalar(
            sa.select(sa.func.count())
            .select_from(m.Ticket)
            .join(m.DrawDay)
            .where(m.DrawDay.label == label, m.Ticket.status == "issued")
        )


# ---------------------------------------------------------------- creating and seeding


def test_only_an_admin_can_use_test_mode(t):
    assert t.arun.post("/api/admin/test-days").status_code == 403


def test_a_test_day_is_labelled_test_and_starts_open(t):
    label = new_day(t)
    assert label.startswith("test-")
    day = t.admin.get(f"/api/admin/draw-days/{label}").json()
    assert (day["kind"], day["status"], day["ticketCount"]) == ("test", "open", 0)


def test_seeding_creates_exactly_the_requested_number_of_paid_tickets(t, db_engine):
    label = new_day(t)
    assert seed(t, label, 203)["ticketCount"] == 203
    assert seed(t, label, 50)["ticketCount"] == 253
    assert ticket_count(db_engine, label) == 253
    with db_engine.connect() as conn:  # every seeded Ticket went through a confirmed (mock) payment
        unpaid = conn.scalar(
            sa.select(sa.func.count())
            .select_from(m.Ticket)
            .join(m.Card)
            .join(m.Order)
            .join(m.Payment, m.Payment.order_id == m.Order.id, isouter=True)
            .where(m.Ticket.draw_day_id.is_not(None), m.Payment.id.is_(None))
        )
    assert unpaid == 0


def test_one_seed_call_is_capped_so_a_request_stays_short(t):
    label = new_day(t)
    res = t.admin.post(f"/api/admin/test-days/{label}/seed", json={"count": 5001})
    assert res.status_code == 422


def test_seeding_15000_tickets_for_a_realistic_draw(t, db_engine):
    label = new_day(t)
    total = 0
    while total < 15000:
        total = seed(t, label, min(2500, 15000 - total))["ticketCount"]
    assert ticket_count(db_engine, label) == 15000


# ---------------------------------------------------------------- the full day


def test_a_full_test_day_runs_end_to_end_and_passes_the_verifier(t, tmp_path):
    label = new_day(t)
    seed(t, label, 300)
    day = close(t, label)
    assert day["status"] == "sealed" and day["ticketCount"] == 300
    seal = json.loads(t.admin.get(f"/api/public/days/{label}/seal.json").content)
    assert seal["kind"] == "test"
    released = round_released_at(seal["drand"]["round"])
    assert released > t.state.test_clock.now()  # the randomness did not exist when the list was sealed

    after_round(t, day)
    sent = t.admin.post(f"/api/admin/draw-days/{label}/otp").json()
    assert "testCode" not in sent  # the code only reaches the Founder's phone, even on test days
    run = t.admin.post(f"/api/admin/draw-days/{label}/run", json={"code": t.state.otp_sender.code}).json()
    assert run["status"] == "published"  # publish gap 0: visible straight after the draw

    for name in ("tickets.csv", "seal.json", "result.json"):
        (tmp_path / name).write_bytes(t.admin.get(f"/api/public/days/{label}/{name}").content)
    (tmp_path / "drand.json").write_text(json.dumps(drand_value(seal["drand"]["round"])))
    report = verify.verify(label, verify.FolderSources(tmp_path))
    assert report.ok, report.render()
    assert "TEST day" in report.render()


def test_a_publish_gap_holds_the_result_back(t):
    label = new_day(t)
    seed(t, label, 50)
    day = close(t, label, gap=10)
    after_round(t, day)
    t.admin.post(f"/api/admin/draw-days/{label}/otp")
    code = t.state.otp_sender.code
    assert t.admin.post(f"/api/admin/draw-days/{label}/run", json={"code": code}).json()["status"] == "drawn"
    assert t.admin.get(f"/api/public/days/{label}/result.json").status_code == 404


def test_closing_twice_or_seeding_after_close_is_refused(t):
    label = new_day(t)
    seed(t, label, 20)
    close(t, label)
    assert t.admin.post(f"/api/admin/test-days/{label}/close", json={}).status_code == 409
    assert t.admin.post(f"/api/admin/test-days/{label}/seed", json={"count": 5}).status_code == 409


def test_test_mode_cannot_touch_a_real_draw_day(t, db_engine):
    real = buy(t.arun, {"p500": 1})["cards"][0]
    assert enter(t.arun, real["id"]).json()["drawDay"] == "2026-11-10"
    for path in ("seed", "close"):
        assert t.admin.post(f"/api/admin/test-days/2026-11-10/{path}", json={"count": 5}).status_code == 404
    label = new_day(t)
    seed(t, label, 40)
    close(t, label)
    csv = t.admin.get(f"/api/public/days/{label}/tickets.csv").text
    assert not set(real["numbers"]) & set(csv.split())
    with db_engine.connect() as conn:
        assert conn.scalar(sa.select(m.DrawDay.status).where(m.DrawDay.label == "2026-11-10")) == "open"
    assert ticket_count(db_engine, "2026-11-10") == 3


def test_a_real_days_otp_is_never_shown_on_screen(make_client):
    from draw_support import sealed_day

    w = sealed_day(make_client)
    at(w.admin, 20, 16)
    assert "testCode" not in w.admin.post("/api/admin/draw-days/2026-11-10/otp").json()


def test_test_days_are_numbered_and_skip_labels_already_sealed_elsewhere(clean_db, session):
    from datetime import UTC, datetime

    from app.draw.testmode import create_test_day

    now = datetime(2026, 11, 10, 12, 0, tzinfo=UTC)
    assert create_test_day(session, now).label == "test-1"
    assert create_test_day(session, now, lambda label: label in {"test-2", "test-3"}).label == "test-4"
    assert create_test_day(session, now).label == "test-5"
