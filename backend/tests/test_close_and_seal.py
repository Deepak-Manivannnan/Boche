"""Entries close at 10 PM IST: the Ticket list is frozen, fingerprinted and sealed on GitHub."""

import hashlib
import json
from datetime import UTC, datetime

import pytest
import sqlalchemy as sa
from test_entries_api import at, enter
from test_orders_api import buy

import verify
from app.core.clock import IST
from app.db import models as m
from engine import canonical_csv

DAY = "2026-11-10"


class FakeSeals:
    """Stands in for the GitHub seals repository."""

    def __init__(self):
        self.files: dict[str, bytes] = {}
        self.calls = 0
        self.fail_next = 0

    def publish(self, label: str, content: bytes):
        self.calls += 1
        if self.fail_next:
            self.fail_next -= 1
            raise OSError("GitHub unreachable")
        self.files.setdefault(label, content)
        return f"sha-{label}", f"https://github.com/acme/seals/blob/main/seals/{label}.json"

    def delete(self, label: str) -> bool:
        if self.fail_next:
            self.fail_next -= 1
            raise OSError("GitHub unreachable")
        return self.files.pop(label, None) is not None


@pytest.fixture
def seals(make_client):
    fake = FakeSeals()
    make_client(None).app.state.seal_publisher = fake
    return fake


def tick(client):
    res = client.post("/api/tick")
    assert res.status_code == 200, res.text
    return res.json()


def day_row(db_engine, label=DAY):
    with db_engine.connect() as conn:
        return conn.execute(sa.select(m.DrawDay).where(m.DrawDay.label == label)).one()


def entered_numbers(client, items=None):
    """Enter 16 lucky numbers (two 1 kg packs) unless told otherwise: a day needs 10 to be sealed."""
    paid = buy(client, items or {"p1k": 2})
    for card in paid["cards"]:
        assert enter(client, card["id"]).status_code == 200
    return [n for card in paid["cards"] for n in card["numbers"]]


def test_nothing_is_sealed_before_ten_pm(make_client, seals, db_engine):
    client = make_client()
    at(client, 21, 0)
    entered_numbers(client)
    at(client, 21, 59, 59)
    tick(client)
    assert day_row(db_engine).status == "open"
    assert client.get(f"/api/public/days/{DAY}/tickets.csv").status_code == 404
    assert seals.calls == 0


def test_at_ten_pm_the_list_is_frozen_and_published_as_the_canonical_csv(make_client, seals, db_engine):
    client = make_client()
    at(client, 18, 0)
    numbers = entered_numbers(client, {"p1k": 2, "p250": 1})
    at(client, 22, 0, 1)
    tick(client)
    day = day_row(db_engine)
    assert day.status == "sealed"
    assert day.ticket_count == 17
    res = client.get(f"/api/public/days/{DAY}/tickets.csv")
    assert res.status_code == 200
    assert res.headers["content-type"].startswith("text/csv")
    assert res.content == canonical_csv(numbers)
    assert day.fingerprint == hashlib.sha256(res.content).hexdigest()


def test_the_seal_names_the_day_count_fingerprint_and_a_round_released_at_ten_fifteen(make_client, seals):
    client = make_client()
    at(client, 18, 0)
    entered_numbers(client)
    at(client, 22, 0, 5)
    tick(client)
    seal = json.loads(seals.files[DAY])
    csv = client.get(f"/api/public/days/{DAY}/tickets.csv").content
    assert seal["scheme"] == "boche-draw-v1"
    assert (seal["draw_day"], seal["kind"], seal["ticket_count"]) == (DAY, "real", 16)
    assert seal["fingerprint"] == hashlib.sha256(csv).hexdigest()
    assert seal["drand"]["chain_hash"] == verify.DRAND_CHAIN
    released = verify.round_time(seal["drand"]["round"])
    assert (
        datetime(2026, 11, 10, 22, 15, tzinfo=IST) <= released < datetime(2026, 11, 10, 22, 15, 3, tzinfo=IST)
    )
    assert datetime.fromisoformat(seal["sealed_at"]) < released


def test_the_seal_on_github_is_exactly_the_one_served_by_the_site(make_client, seals):
    client = make_client()
    at(client, 18, 0)
    entered_numbers(client)
    at(client, 22, 1)
    tick(client)
    assert client.get(f"/api/public/days/{DAY}/seal.json").content == seals.files[DAY]


def test_closing_again_changes_nothing_and_publishes_once(make_client, seals, db_engine):
    client = make_client()
    at(client, 18, 0)
    entered_numbers(client)
    at(client, 22, 0, 1)
    tick(client)
    first = day_row(db_engine)
    at(client, 22, 5)
    tick(client)
    again = day_row(db_engine)
    assert (again.fingerprint, again.drand_round, again.sealed_at) == (
        first.fingerprint,
        first.drand_round,
        first.sealed_at,
    )
    assert seals.calls == 1


def test_a_failed_github_commit_is_retried_without_changing_the_seal(make_client, seals, db_engine):
    client = make_client()
    at(client, 18, 0)
    entered_numbers(client)
    seals.fail_next = 1
    at(client, 22, 0, 1)
    tick(client)
    assert day_row(db_engine).seal_commit_sha is None
    sealed = day_row(db_engine).seal_json
    at(client, 22, 0, 40)
    tick(client)
    day = day_row(db_engine)
    assert day.seal_commit_sha == f"sha-{DAY}"
    assert day.seal_url.endswith(f"/seals/{DAY}.json")
    assert seals.files[DAY].decode() == day.seal_json == sealed


def test_cancelled_tickets_and_entries_for_tomorrow_are_not_in_the_list(make_client, seals, db_engine):
    arun, admin = make_client("arun"), make_client("admin")
    at(arun, 18, 0)
    kept = entered_numbers(arun)
    refunded = buy(arun, {"p500": 1})
    enter(arun, refunded["cards"][0]["id"])
    admin.post(f"/api/admin/orders/{refunded['id']}/refund")
    at(arun, 22, 0, 0)
    tomorrow = buy(arun, {"p250": 1})
    assert enter(arun, tomorrow["cards"][0]["id"]).json()["drawDay"] == "2026-11-11"
    tick(arun)
    assert arun.get(f"/api/public/days/{DAY}/tickets.csv").content == canonical_csv(kept)


def test_a_late_seal_picks_a_round_still_in_the_future(make_client, seals, db_engine):
    """If the server was asleep and only seals at 10:20 PM, the 10:15 round is already public. Sealing must
    then name a round that nobody can know yet, or someone could choose the list to suit the randomness."""
    client = make_client()
    at(client, 18, 0)
    entered_numbers(client)
    at(client, 22, 20)
    tick(client)
    day = day_row(db_engine)
    assert verify.round_time(day.drand_round) > day.sealed_at.replace(tzinfo=UTC)
    assert day.draw_not_before.replace(tzinfo=UTC) >= verify.round_time(day.drand_round)


def test_any_api_request_after_ten_pm_closes_the_day_even_without_a_tick(make_client, seals, db_engine):
    client = make_client()
    at(client, 18, 0)
    entered_numbers(client)
    at(client, 22, 3)
    client.get("/api/me")
    assert day_row(db_engine).status == "sealed"


def test_without_a_github_token_the_day_still_closes_and_waits_to_publish(make_client, db_engine):
    client = make_client()
    client.app.state.seal_publisher = None
    at(client, 18, 0)
    entered_numbers(client)
    at(client, 22, 1)
    assert tick(client)["unpublished"] == [DAY]
    assert day_row(db_engine).status == "sealed"


def test_an_unknown_day_has_no_ticket_list(make_client):
    assert make_client(None).get("/api/public/days/1999-01-01/tickets.csv").status_code == 404


def test_a_scheduler_ping_by_get_seals_once_and_repeat_pings_change_nothing(make_client, seals, db_engine):
    client = make_client()
    at(client, 18, 0)
    entered_numbers(client)
    at(client, 22, 0, 1)
    assert client.get("/api/tick").status_code == 200
    assert client.get("/api/tick").status_code == 200
    assert day_row(db_engine).status == "sealed"
    assert seals.calls == 1
