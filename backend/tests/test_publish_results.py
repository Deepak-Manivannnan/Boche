"""Ticket 10: results are published at 8:30 PM IST (or right after a later draw), Customers see their outcome,
Claims are stored on the server, and the public files of a Draw day pass the real Verifier."""

import json

import pytest
import sqlalchemy as sa
from draw_support import DAY, drand_value, draw, sealed_day
from test_entries_api import at

import verify
from app import models as m

RESULT = f"/api/public/days/{DAY}/result.json"


@pytest.fixture
def w(make_client):
    return sealed_day(make_client)


def my_cards(client):
    return [c for o in client.get("/api/me/orders").json() for c in o["cards"]]


def winning_card(w, result):
    won = {x["ticket"] for x in result["winners"]}
    return next(c for c in w.cards if won & set(c["numbers"]))


# ---------------------------------------------------------------- when results become visible


def test_nothing_is_public_before_eight_thirty_even_after_the_draw(w):
    draw(w)
    at(w.arun, 20, 29, 59)
    w.arun.post("/api/tick")
    assert w.arun.get(RESULT).status_code == 404
    assert all(d["label"] != DAY or d["winners"] is None for d in w.arun.get("/api/public/days").json())


def test_at_eight_thirty_the_result_is_published(w, db_engine):
    drawn = draw(w)
    at(w.arun, 20, 30, 0)
    w.arun.post("/api/tick")
    res = w.arun.get(RESULT)
    assert res.status_code == 200
    body = res.json()
    assert [x["ticket"] for x in body["winners"]] == [x["ticket"] for x in drawn["winners"]]
    with db_engine.connect() as conn:
        assert conn.scalar(sa.select(m.DrawDay.status).where(m.DrawDay.label == DAY)) == "published"


def test_a_draw_after_eight_thirty_is_published_straight_away(w):
    draw(w, 21, 10)
    assert w.arun.get(RESULT).status_code == 200


def test_an_undrawn_day_is_never_published(w):
    at(w.arun, 23, 0)
    w.arun.post("/api/tick")
    assert w.arun.get(RESULT).status_code == 404


# ---------------------------------------------------------------- what the public sees


def test_the_public_result_shows_masked_winners_and_no_private_data(w):
    draw(w, 20, 40)
    body = w.arun.get(RESULT).json()
    assert body["winners"][0]["name"] == "Arun T."  # "Arun Tester" -> first name and last initial
    text = json.dumps(body)
    assert "arun@example.com" not in text and "Tester" not in text


def test_the_public_days_list_carries_each_published_result(w):
    draw(w, 20, 40)
    days = w.arun.get("/api/public/days").json()
    day = next(d for d in days if d["label"] == DAY)
    assert day["status"] == "published" and len(day["winners"]) == 10
    assert day["ticketCount"] == 16 and day["fingerprint"]


def test_a_draw_days_public_files_pass_the_real_verifier(w, tmp_path):
    draw(w, 20, 40)
    (tmp_path / "tickets.csv").write_bytes(w.arun.get(f"/api/public/days/{DAY}/tickets.csv").content)
    (tmp_path / "seal.json").write_bytes(w.arun.get(f"/api/public/days/{DAY}/seal.json").content)
    (tmp_path / "result.json").write_bytes(w.arun.get(RESULT).content)
    round_no = json.loads((tmp_path / "seal.json").read_text())["drand"]["round"]
    (tmp_path / "drand.json").write_text(json.dumps(drand_value(round_no)))
    report = verify.verify(DAY, verify.FolderSources(tmp_path))
    assert report.ok, report.render()


# ---------------------------------------------------------------- what each Customer sees


def test_each_card_shows_whether_it_was_in_the_sealed_list(w, make_client):
    cards = my_cards(w.arun)
    assert all(c["included"] is True for c in cards)
    late = make_client("meera")
    from test_orders_api import buy

    unentered = buy(late, {"p250": 1})["cards"][0]
    assert next(c for c in my_cards(late) if c["id"] == unentered["id"])["included"] is None


def test_a_customer_sees_their_own_wins_only_after_publish(w):
    result = draw(w)
    card = winning_card(w, result)
    assert next(c for c in my_cards(w.arun) if c["id"] == card["id"])["wins"] == []
    at(w.arun, 20, 30)
    w.arun.post("/api/tick")
    wins = next(c for c in my_cards(w.arun) if c["id"] == card["id"])["wins"]
    assert wins and {x["ticket"] for x in wins} <= set(card["numbers"])
    assert all(x["amount"] in (100000, 50000, 25000, 10000) for x in wins)


# ---------------------------------------------------------------- claims


def test_a_winner_can_claim_once_and_the_claim_is_stored(w):
    card = winning_card(w, draw(w, 20, 40))
    res = w.arun.post("/api/claims", json={"cardId": card["id"]})
    assert res.status_code == 201, res.text
    claim = res.json()
    assert claim["ref"].startswith("CLM-") and claim["amount"] > 0
    assert w.arun.post("/api/claims", json={"cardId": card["id"]}).json() == claim
    assert next(c for c in my_cards(w.arun) if c["id"] == card["id"])["claim"]["ref"] == claim["ref"]


def test_a_card_without_a_winning_ticket_cannot_be_claimed(make_client):
    # 12 single-Ticket cards and only 10 Winners: at least two cards must lose.
    w = sealed_day(make_client, packs=1, single_cards=12)
    won = {x["ticket"] for x in draw(w, 20, 40)["winners"]}
    loser = next(c for c in w.cards if not won & set(c["numbers"]))
    assert w.arun.post("/api/claims", json={"cardId": loser["id"]}).status_code == 409


def test_a_win_cannot_be_claimed_before_results_are_published(w):
    card = winning_card(w, draw(w))
    assert w.arun.post("/api/claims", json={"cardId": card["id"]}).status_code == 409


def test_nobody_can_claim_someone_elses_card(w, make_client):
    card = winning_card(w, draw(w, 20, 40))
    assert make_client("meera").post("/api/claims", json={"cardId": card["id"]}).status_code == 404
