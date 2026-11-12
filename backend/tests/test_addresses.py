"""Saved delivery addresses are stored per account on the server: two Customers on the same browser never
see or change each other's addresses."""

from api_support import google_sign_up
from test_orders_api import DELIVERY, buy

HOME = {**DELIVERY, "label": "Home"}
WORK = {
    "label": "Work",
    "name": "Arun Mathew",
    "house": "Infopark Phase 1",
    "street": "Kakkanad Road",
    "pin": "682042",
    "po": "Kakkanad",
    "district": "Ernakulam",
}


def save(client, address):
    return client.post("/api/me/addresses", json=address)


def mine(client):
    res = client.get("/api/me/addresses")
    assert res.status_code == 200, res.text
    return res.json()


def test_a_new_account_has_no_saved_address(make_client):
    assert mine(make_client("arun")) == []


def test_the_first_address_is_the_default_and_more_can_be_added(make_client):
    arun = make_client("arun")
    first = save(arun, HOME)
    assert first.status_code == 201 and first.json()["default"] is True
    second = save(arun, WORK)
    assert second.status_code == 201 and second.json()["default"] is False
    assert [(a["label"], a["default"]) for a in mine(arun)] == [("Home", True), ("Work", False)]


def test_two_accounts_on_the_same_browser_never_see_each_others_addresses(make_client):
    arun, meera = make_client("arun"), make_client("meera")
    a = save(arun, HOME).json()
    assert mine(meera) == []
    assert meera.put(f"/api/me/addresses/{a['id']}", json=WORK).status_code == 404
    assert meera.post(f"/api/me/addresses/{a['id']}/default").status_code == 404
    assert meera.delete(f"/api/me/addresses/{a['id']}").status_code == 404
    assert mine(arun) == [a]  # unchanged

    save(meera, WORK)
    assert [x["label"] for x in mine(meera)] == ["Work"]
    assert [x["label"] for x in mine(arun)] == ["Home"]


def test_signing_out_and_in_as_someone_else_shows_only_their_addresses(make_client):
    browser = make_client("arun")
    save(browser, HOME)
    browser.post("/api/auth/logout")
    assert browser.get("/api/me/addresses").status_code == 401
    google_sign_up(browser, "meera")
    assert mine(browser) == []


def test_the_same_place_saved_again_updates_it_instead_of_adding_a_copy(make_client):
    arun = make_client("arun")
    first = save(arun, HOME).json()
    again = save(arun, {**HOME, "house": "  rose villa, 12/345 ", "name": "Arun M", "label": "Other"})
    assert again.status_code == 200 and again.json()["id"] == first["id"]
    assert [(a["name"], a["label"]) for a in mine(arun)] == [("Arun M", "Other")]


def test_editing_choosing_the_default_and_deleting(make_client):
    arun = make_client("arun")
    home, work = save(arun, HOME).json(), save(arun, WORK).json()
    res = arun.put(f"/api/me/addresses/{work['id']}", json={**WORK, "street": "CSEZ Road"})
    assert res.status_code == 200 and res.json()["street"] == "CSEZ Road"

    listed = arun.post(f"/api/me/addresses/{work['id']}/default").json()
    assert [a["default"] for a in listed] == [False, True]

    assert arun.delete(f"/api/me/addresses/{work['id']}").status_code == 204
    assert [(a["id"], a["default"]) for a in mine(arun)] == [(home["id"], True)]  # the default moves on


def test_addresses_follow_the_same_rules_as_a_delivery(make_client):
    arun = make_client("arun")
    assert save(arun, {**HOME, "pin": "560001"}).status_code == 422  # Kerala only
    assert save(arun, {**HOME, "label": "Office"}).status_code == 422
    assert save(arun, {**HOME, "name": "A"}).status_code == 422


def test_only_a_signed_in_customer_has_addresses(make_client):
    stranger = make_client(None)
    assert stranger.get("/api/me/addresses").status_code == 401
    assert save(stranger, HOME).status_code == 401


def test_an_order_keeps_its_own_copy_of_the_address(make_client):
    arun = make_client("arun")
    saved = save(arun, HOME).json()
    order = buy(arun, {"p250": 1})
    arun.put(f"/api/me/addresses/{saved['id']}", json={**HOME, "street": "Somewhere else"})
    arun.delete(f"/api/me/addresses/{saved['id']}")
    orders = arun.get("/api/me/orders").json()
    assert next(o for o in orders if o["id"] == order["id"])["delivery"]["street"] == DELIVERY["street"]


def test_there_is_a_sensible_limit(make_client):
    arun = make_client("arun")
    for i in range(20):
        assert save(arun, {**HOME, "house": f"House {i}"}).status_code == 201
    res = save(arun, {**HOME, "house": "House 21"})
    assert res.status_code == 409 and "20" in res.json()["detail"]
