"""Signing up and in with a mobile number and SMS code, alongside Google.

- Continue with Google (new customer): verify a mobile number, create the profile, then the account exists.
- Continue with mobile number (new number): verify it, create the profile; that account signs in by number
  only until it connects a Google account from the profile.
- A number belongs to one account: a Google sign-up with a registered number is refused straight away."""

import sqlalchemy as sa
from api_support import complete_signup, google_sign_up, mobile_for

from app.db import models as m

ADDRESS = {
    "name": "Meera K",
    "house": "Lotus House",
    "street": "MG Road",
    "pin": "695001",
    "po": "Thiruvananthapuram",
    "district": "Thiruvananthapuram",
}


def sms(client):
    return client.app.state.login_sms_sender


def send(client, mobile):
    return client.post("/api/auth/otp/send", json={"mobile": mobile})


def verify(client, mobile, code=None):
    return client.post(
        "/api/auth/otp/verify", json={"mobile": mobile, "code": code or sms(client).code_for(mobile)}
    )


def mobile_sign_in(client, mobile):
    assert send(client, mobile).status_code == 200
    return verify(client, mobile)


def users(db_engine):
    with db_engine.connect() as conn:
        return conn.execute(sa.select(m.User.name, m.User.mobile, m.User.email)).all()


# ---------------------------------------------------------------- Continue with Google


def test_a_new_google_customer_must_verify_a_mobile_and_create_a_profile_first(make_client, db_engine):
    browser = make_client(None)
    res = browser.post("/api/auth/google", json={"credential": "arun-token-xxxxxxxxxx"})
    assert res.json()["signup"] == {
        "step": "mobile",
        "via": "google",
        "name": "Arun Tester",
        "email": "arun@example.com",
        "mobile": None,
    }
    assert browser.get("/api/me").status_code == 401 and users(db_engine) == []  # no account yet

    mobile = "9847012345"
    assert send(browser, mobile).status_code == 200
    step = verify(browser, mobile).json()["signup"]
    assert (step["step"], step["name"], step["mobile"]) == ("profile", "Arun Tester", mobile)
    assert browser.get("/api/me").status_code == 401 and users(db_engine) == []

    me = browser.post("/api/auth/signup", json={"name": "Arun Mathew", "age": 34}).json()
    assert (me["name"], me["email"], me["mobile"], me["age"], me["hasGoogle"]) == (
        "Arun Mathew",
        "arun@example.com",
        mobile,
        34,
        True,
    )
    assert browser.get("/api/me").json() == me


def test_a_google_sign_up_with_a_registered_number_is_refused_straight_away(make_client):
    google_sign_up(make_client(None), "arun", "9847012345")
    meera = make_client(None)
    meera.post("/api/auth/google", json={"credential": "meera-token-xxxxxxxxxx"})
    res = send(meera, "98470 12345")
    assert res.status_code == 409 and "already registered" in res.json()["detail"]
    assert len([s for s in sms(meera).sent if s[0] == "9847012345"]) == 1  # only Arun's code; none for Meera
    assert meera.get("/api/me").status_code == 401
    assert send(meera, "9847000001").status_code == 200  # a different number is fine


def test_a_google_account_made_this_way_can_also_sign_in_with_its_number(make_client):
    arun = make_client(None)
    me = google_sign_up(arun, "arun", "9847012345").json()
    arun.post("/api/auth/logout")
    again = make_client(None)
    assert mobile_sign_in(again, "9847012345").json()["id"] == me["id"]


# ---------------------------------------------------------------- Continue with mobile number


def test_a_new_number_creates_a_profile_and_signs_in_with_the_number_only(make_client, db_engine):
    browser = make_client(None)
    step = mobile_sign_in(browser, "9847099999").json()["signup"]
    assert (step["step"], step["via"], step["name"]) == ("profile", "mobile", "")
    me = browser.post("/api/auth/signup", json={"name": "Meera K", "age": 29}).json()
    assert (me["name"], me["mobile"], me["email"], me["hasGoogle"]) == ("Meera K", "9847099999", None, False)

    browser.post("/api/auth/logout")
    assert mobile_sign_in(browser, "9847099999").json()["id"] == me["id"]  # signs in by number
    browser.post("/api/auth/logout")
    other = browser.post("/api/auth/google", json={"credential": "meera-token-xxxxxxxxxx"}).json()
    assert "signup" in other  # a Google account is not this account: it would be a new sign-up
    assert len(users(db_engine)) == 1


def test_a_mobile_account_can_connect_google_and_then_sign_in_with_either(make_client):
    browser = make_client(None)
    mobile_sign_in(browser, "9847099999")
    me = browser.post("/api/auth/signup", json={"name": "Meera K", "age": 29}).json()
    connected = browser.post("/api/me/google", json={"credential": "meera-token-xxxxxxxxxx"})
    assert connected.status_code == 200
    assert (connected.json()["email"], connected.json()["hasGoogle"], connected.json()["name"]) == (
        "meera@example.com",
        True,
        "Meera K",  # her own name stays
    )
    browser.post("/api/auth/logout")
    assert (
        browser.post("/api/auth/google", json={"credential": "meera-token-xxxxxxxxxx"}).json()["id"]
        == me["id"]
    )
    browser.post("/api/auth/logout")
    assert mobile_sign_in(browser, "9847099999").json()["id"] == me["id"]
    assert browser.post("/api/me/google", json={"credential": "meera-token-xxxxxxxxxx"}).status_code == 409


def test_a_google_account_already_used_cannot_be_connected_to_another(make_client):
    make_client("arun")  # arun@example.com has an account
    browser = make_client(None)
    mobile_sign_in(browser, "9847099999")
    browser.post("/api/auth/signup", json={"name": "Meera K", "age": 29})
    res = browser.post("/api/me/google", json={"credential": "arun-token-xxxxxxxxxx"})
    assert res.status_code == 409
    assert res.json()["detail"] == (
        "This Google account is already linked to another account. Please try again with a different account."
    )
    assert browser.get("/api/me").json()["hasGoogle"] is False  # nothing changed on Meera's account


# ---------------------------------------------------------------- the profile


def test_the_profile_needs_a_name_and_an_adult_age_and_the_address_is_optional(make_client, db_engine):
    browser = make_client(None)
    mobile_sign_in(browser, "9847099999")
    assert browser.post("/api/auth/signup", json={"name": "Meera K"}).status_code == 422
    assert browser.post("/api/auth/signup", json={"name": "M", "age": 29}).status_code == 422
    assert browser.post("/api/auth/signup", json={"name": "Meera K", "age": 17}).status_code == 422
    me = browser.post("/api/auth/signup", json={"name": "Meera K", "age": 29, "address": ADDRESS})
    assert me.status_code == 200
    saved = browser.get("/api/me/addresses").json()
    assert [(a["label"], a["default"], a["house"]) for a in saved] == [("Home", True, "Lotus House")]


def test_no_profile_without_a_verified_number(make_client):
    browser = make_client(None)
    assert browser.post("/api/auth/signup", json={"name": "Meera K", "age": 29}).status_code == 409
    browser.post("/api/auth/google", json={"credential": "meera-token-xxxxxxxxxx"})
    assert browser.post("/api/auth/signup", json={"name": "Meera K", "age": 29}).status_code == 409


def test_the_name_can_be_changed_any_time(make_client):
    arun = make_client("arun")
    assert arun.patch("/api/me", json={"name": "Arun Mathew"}).json()["name"] == "Arun Mathew"
    assert arun.get("/api/me").json()["name"] == "Arun Mathew"
    assert arun.patch("/api/me", json={"name": " "}).status_code == 422


def test_a_tampered_sign_up_cookie_counts_for_nothing(make_client):
    browser = make_client(None)
    mobile_sign_in(browser, "9847099999")
    raw = browser.cookies.get("boche_signup")
    browser.cookies.clear()
    browser.cookies.set("boche_signup", raw[:-4] + ("0000" if not raw.endswith("0000") else "1111"))
    assert browser.post("/api/auth/signup", json={"name": "Meera K", "age": 29}).status_code == 409


# ---------------------------------------------------------------- the codes


def test_codes_are_four_digits_sent_only_by_sms_and_used_once(make_client):
    browser = make_client(None)
    res = send(browser, "+91 98470 99999")
    assert res.json() == {"sent": True, "mobile": "9847099999"}  # the code is never in a response
    code = sms(browser).code_for("9847099999")
    assert len(code) == 4 and code.isdigit()
    assert verify(browser, "9847099999", code).status_code == 200
    assert verify(browser, "9847099999", code).status_code == 409  # used


def test_a_wrong_code_is_counted_and_five_wrong_codes_lock_it(make_client):
    browser = make_client(None)
    send(browser, "9847099999")
    right = sms(browser).code_for("9847099999")
    wrong = "0000" if right != "0000" else "1111"
    for left in (4, 3, 2, 1):
        res = verify(browser, "9847099999", wrong)
        assert res.status_code == 401 and f"{left} tries left" in res.json()["detail"]
    assert verify(browser, "9847099999", wrong).status_code == 429
    assert verify(browser, "9847099999", right).status_code == 429  # locked: ask for a new code


def test_a_code_expires_after_ten_minutes(make_client):
    browser = make_client(None)
    send(browser, "9847099999")
    browser.app.state.test_clock.advance(minutes=10)
    assert verify(browser, "9847099999").status_code == 401


def test_sending_is_limited_per_number(make_client):
    browser = make_client(None)
    clock = browser.app.state.test_clock
    assert send(browser, "9847099999").status_code == 200
    res = send(browser, "9847099999")
    assert res.status_code == 429 and "Wait" in res.json()["detail"]
    for _ in range(4):
        clock.advance(seconds=61)
        assert send(browser, "9847099999").status_code == 200
    clock.advance(seconds=61)
    assert send(browser, "9847099999").status_code == 429  # five an hour
    clock.advance(hours=1)
    assert send(browser, "9847099999").status_code == 200


def test_only_indian_mobile_numbers(make_client):
    browser = make_client(None)
    for bad in ("12345", "5847099999", "98470999990"):
        assert send(browser, bad).status_code == 422, bad


# ---------------------------------------------------------------- existing accounts and admins


def test_an_account_made_before_mobile_sign_in_still_signs_in_with_google(make_client, db_engine):
    with db_engine.begin() as conn:  # an account from before: Google only, no number
        conn.execute(
            sa.insert(m.User).values(
                google_sub="g-arun", email="arun@example.com", name="Arun Tester", role="customer"
            )
        )
    browser = make_client(None)
    me = browser.post("/api/auth/google", json={"credential": "arun-token-xxxxxxxxxx"}).json()
    assert (me["name"], me["mobile"]) == ("Arun Tester", None)  # signed in straight away, as before


def test_an_admin_signs_in_with_google_without_a_mobile_step(make_client):
    body = {"credential": "admin-token-xxxxxxxxxx", "admin": True}  # on the admin page
    me = make_client(None).post("/api/auth/google", json=body).json()
    assert me["role"] == "admin" and "signup" not in me


def test_test_customers_get_distinct_numbers():
    assert len({mobile_for(n) for n in ("arun", "meera", "admin", "ravi", "deepak")}) == 5


def test_a_code_still_works_just_before_it_expires(make_client):
    browser = make_client(None)
    send(browser, "9847099999")
    browser.app.state.test_clock.advance(minutes=9, seconds=59)
    assert verify(browser, "9847099999").status_code == 200


def test_the_signup_helper_used_by_other_tests_makes_a_real_account(make_client):
    browser = make_client(None)
    browser.post("/api/auth/google", json={"credential": "ravi-token-xxxxxxxxxx"})
    assert complete_signup(browser, "9847011111", "Ravi Tester").json()["mobile"] == "9847011111"
