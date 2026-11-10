"""Buying tea: server-side pricing, mock payment with a signed confirmation, and Ticket issuing."""

import hashlib
import hmac
import json
import re

import pytest
import sqlalchemy as sa
from api_support import PAYMENT_SECRET

from app import models as m

LUCKY_NUMBER = re.compile(r"^[ABCDEFGHJKLMNPRSTUVWXYZ]{2} \d{6}$")
DELIVERY = {
    "name": "Arun Mathew",
    "house": "Rose Villa, 12/345",
    "street": "Seaport-Airport Road",
    "pin": "682030",
    "po": "Kakkanad",
    "district": "Ernakulam",
}


def order(client, items, **extra):
    return client.post("/api/orders", json={"items": items, "delivery": DELIVERY, **extra})


def buy(client, items):
    created = order(client, items)
    assert created.status_code == 201, created.text
    paid = client.post(f"/api/payments/mock/{created.json()['id']}/pay")
    assert paid.status_code == 200, paid.text
    return paid.json()


def ticket_count(db_engine) -> int:
    with db_engine.connect() as conn:
        return conn.scalar(sa.select(sa.func.count()).select_from(m.Ticket))


def signed(body: bytes, secret: str = PAYMENT_SECRET) -> dict:
    return {
        "X-Mockpay-Signature": "sha256=" + hmac.new(secret.encode(), body, hashlib.sha256).hexdigest(),
        "Content-Type": "application/json",
    }


def captured(order_id: str, amount: int, ref: str = "mockpay_test_1") -> bytes:
    return json.dumps(
        {"event": "payment.captured", "provider_ref": ref, "order_id": order_id, "amount_paise": amount}
    ).encode()


# ---------------------------------------------------------------- pricing


def test_the_server_prices_an_order_with_gst_and_logistics(make_client):
    # 2 x 1 kg (Rs 320, logistics Rs 52) + 1 x 250 g (Rs 90, logistics Rs 36)
    # tea Rs 730, logistics Rs 140, GST 5% of 730 = 36.50 + 18% of 140 = 25.20 = 61.70, rounded up to Rs 62
    body = order(make_client(), {"p1k": 2, "p250": 1}).json()
    assert body["subtotalPaise"] == 73000
    assert body["logisticsPaise"] == 14000
    assert body["teaGstPaise"] == 3650
    assert body["logisticsGstPaise"] == 2520
    assert body["gstPaise"] == 6200
    assert body["totalPaise"] == 93200
    assert body["status"] == "pending"


def test_gst_is_rounded_up_to_the_next_whole_rupee_like_the_checkout_screen(make_client):
    # 1 x 250 g: tea Rs 90 + logistics Rs 36; GST 4.50 + 6.48 = 10.98 -> Rs 11; total Rs 137
    body = order(make_client(), {"p250": 1}).json()
    assert (body["gstPaise"], body["totalPaise"]) == (1100, 13700)


def test_prices_and_counts_sent_by_the_browser_are_ignored(make_client):
    res = order(make_client(), {"p250": 1}, totalPaise=1, subtotalPaise=1, numbers=99, tickets=99)
    assert res.status_code == 201
    assert res.json()["totalPaise"] == 13700


@pytest.mark.parametrize(
    "items",
    [
        pytest.param({}, id="empty"),
        pytest.param({"p250": 0}, id="all-zero"),
        pytest.param({"p2kg": 1}, id="unknown-pack"),
        pytest.param({"p250": 11}, id="over-max-quantity"),
        pytest.param({"p250": -1}, id="negative"),
        pytest.param({"p250": 1.5}, id="fractional"),
    ],
)
def test_invalid_baskets_are_refused(make_client, items):
    assert order(make_client(), items).status_code == 422


@pytest.mark.parametrize("pin", ["560001", "68203", "abcdef", ""])
def test_delivery_outside_kerala_or_with_a_bad_pincode_is_refused(make_client, pin):
    res = make_client().post("/api/orders", json={"items": {"p250": 1}, "delivery": {**DELIVERY, "pin": pin}})
    assert res.status_code == 422


def test_ordering_needs_a_signed_in_customer(make_client):
    assert order(make_client(None), {"p250": 1}).status_code == 401


# ---------------------------------------------------------------- payment and tickets


def test_no_tickets_exist_until_the_payment_is_confirmed(make_client, db_engine):
    client = make_client()
    order(client, {"p1k": 1})
    assert ticket_count(db_engine) == 0
    assert client.get("/api/me/orders").json() == []


def test_paying_issues_one_scratch_card_per_pack_with_its_advertised_lucky_numbers(make_client, db_engine):
    paid = buy(make_client(), {"p1k": 2, "p500": 1, "p250": 1})
    assert paid["status"] == "paid"
    counts = sorted(len(card["numbers"]) for card in paid["cards"])
    assert counts == [1, 3, 8, 8]
    assert ticket_count(db_engine) == 20


def test_lucky_numbers_have_the_prototype_format_and_are_all_different(make_client):
    client = make_client()
    numbers = [n for _ in range(5) for card in buy(client, {"p1k": 10})["cards"] for n in card["numbers"]]
    assert len(numbers) == 400
    assert all(LUCKY_NUMBER.match(n) for n in numbers), numbers[:5]
    assert len(set(numbers)) == 400


def test_a_confirmation_with_a_wrong_signature_issues_nothing(make_client, db_engine):
    client = make_client()
    o = order(client, {"p1k": 1}).json()
    body = captured(o["id"], o["totalPaise"])
    for headers in (
        signed(body, "not-the-secret"),
        {"Content-Type": "application/json"},
        {"X-Mockpay-Signature": "sha256=zz", "Content-Type": "application/json"},
    ):
        assert client.post("/api/payments/webhook", content=body, headers=headers).status_code == 401
    assert ticket_count(db_engine) == 0


def test_a_confirmation_delivered_twice_issues_tickets_once(make_client, db_engine):
    client = make_client()
    o = order(client, {"p1k": 1}).json()
    body = captured(o["id"], o["totalPaise"])
    first = client.post("/api/payments/webhook", content=body, headers=signed(body))
    again = client.post("/api/payments/webhook", content=body, headers=signed(body))
    assert (first.status_code, again.status_code) == (200, 200)
    assert ticket_count(db_engine) == 8


def test_a_second_different_payment_for_a_paid_order_issues_nothing_more(make_client, db_engine):
    client = make_client()
    o = order(client, {"p1k": 1}).json()
    for i, expected in ((1, 200), (2, 409)):
        body = captured(o["id"], o["totalPaise"], ref=f"mockpay_{i}")
        assert (
            client.post("/api/payments/webhook", content=body, headers=signed(body)).status_code == expected
        )
    assert ticket_count(db_engine) == 8


def test_a_confirmation_for_the_wrong_amount_is_refused(make_client, db_engine):
    client = make_client()
    o = order(client, {"p1k": 1}).json()
    body = captured(o["id"], o["totalPaise"] - 100)
    assert client.post("/api/payments/webhook", content=body, headers=signed(body)).status_code == 400
    assert ticket_count(db_engine) == 0


def test_a_confirmation_for_an_unknown_order_is_refused(make_client):
    body = captured("TEA-NOPE", 100)
    assert make_client().post("/api/payments/webhook", content=body, headers=signed(body)).status_code == 404


def test_paying_again_for_a_paid_order_returns_it_without_new_tickets(make_client, db_engine):
    client = make_client()
    o = order(client, {"p250": 1}).json()
    client.post(f"/api/payments/mock/{o['id']}/pay")
    again = client.post(f"/api/payments/mock/{o['id']}/pay")
    assert again.status_code == 200
    assert ticket_count(db_engine) == 1


def test_a_customer_cannot_pay_for_someone_elses_order(make_client, db_engine):
    arun, meera = make_client("arun"), make_client("meera")
    o = order(arun, {"p1k": 1}).json()
    assert meera.post(f"/api/payments/mock/{o['id']}/pay").status_code == 404
    assert ticket_count(db_engine) == 0


# ---------------------------------------------------------------- my orders and scratching


def test_my_orders_lists_paid_orders_newest_first_with_everything_the_screens_need(make_client):
    client = make_client()
    first = buy(client, {"p250": 1})
    second = buy(client, {"p1k": 1, "p500": 2})
    orders = client.get("/api/me/orders").json()
    assert [o["id"] for o in orders] == [second["id"], first["id"]]
    latest = orders[0]
    assert latest["delivery"] == DELIVERY
    assert [(i["packId"], i["size"], i["qty"], i["unitPricePaise"]) for i in latest["items"]] == [
        ("p500", "500 g", 2, 17000),
        ("p1k", "1 kg", 1, 32000),
    ]
    assert [c["id"] for c in latest["cards"]] == [f"{latest['id']}-{n}" for n in (1, 2, 3)]
    assert all(c["scratched"] is False for c in latest["cards"])
    assert isinstance(latest["ts"], int)


def test_customers_see_only_their_own_orders(make_client):
    arun, meera = make_client("arun"), make_client("meera")
    buy(arun, {"p250": 1})
    assert meera.get("/api/me/orders").json() == []


def test_scratching_a_card_is_remembered(make_client):
    client = make_client()
    card = buy(client, {"p500": 1})["cards"][0]
    assert client.post(f"/api/cards/{card['id']}/scratch").status_code == 200
    assert client.post(f"/api/cards/{card['id']}/scratch").status_code == 200  # repeat is harmless
    assert client.get("/api/me/orders").json()[0]["cards"][0]["scratched"] is True


def test_a_customer_cannot_scratch_someone_elses_card(make_client):
    arun, meera = make_client("arun"), make_client("meera")
    card = buy(arun, {"p500": 1})["cards"][0]
    assert meera.post(f"/api/cards/{card['id']}/scratch").status_code == 404
    assert arun.get("/api/me/orders").json()[0]["cards"][0]["scratched"] is False
