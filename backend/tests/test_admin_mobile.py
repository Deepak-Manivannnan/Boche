"""Admins sign in with a mobile number and SMS code as well as Google. Codes go only to numbers on
ADMIN_MOBILES: any other number is refused before a code is made or an SMS is sent, and admin rights are
re-checked against the lists on every request."""

from dataclasses import replace

import sqlalchemy as sa

from app.core.config import admin_mobiles
from app.db import models as m

ADMIN = "9847000001"


def admin_list(client, *numbers):
    state = client.app.state
    state.settings = replace(state.settings, admin_mobiles=frozenset(numbers))


def sms(client):
    return client.app.state.login_sms_sender


def send(client, mobile):
    return client.post("/api/auth/admin/otp/send", json={"mobile": mobile})


def verify(client, mobile, code=None):
    code = code or sms(client).code_for(mobile)
    return client.post("/api/auth/admin/otp/verify", json={"mobile": mobile, "code": code})


def test_a_listed_number_signs_in_as_admin(make_client):
    browser = make_client(None)
    admin_list(browser, ADMIN)
    assert send(browser, "+91 98470 00001").json() == {"sent": True, "mobile": ADMIN}
    me = verify(browser, ADMIN).json()
    assert (me["role"], me["mobile"], me["name"]) == ("admin", ADMIN, "Admin")
    assert browser.get("/api/admin/draw-days").status_code == 200


def test_any_other_number_gets_no_code_and_no_sms(make_client, db_engine):
    browser = make_client(None)
    admin_list(browser, ADMIN)
    res = send(browser, "9847000002")
    assert res.status_code == 403 and res.json()["detail"] == "This number is not an admin number"
    assert sms(browser).sent == []  # nothing went out
    with db_engine.connect() as conn:
        assert conn.scalar(sa.select(sa.func.count()).select_from(m.LoginOtp)) == 0  # no code was even made
    assert verify(browser, "9847000002", "1234").status_code == 403
    assert browser.get("/api/me").status_code == 401


def test_with_no_admin_numbers_set_nobody_gets_a_code(make_client):
    browser = make_client(None)
    admin_list(browser)
    assert send(browser, ADMIN).status_code == 403 and sms(browser).sent == []


def test_taking_a_number_off_the_list_ends_access_at_once(make_client):
    browser = make_client(None)
    admin_list(browser, ADMIN)
    send(browser, ADMIN)
    verify(browser, ADMIN)
    assert browser.get("/api/admin/draw-days").status_code == 200
    admin_list(browser)  # removed in Render
    assert browser.get("/api/admin/draw-days").status_code == 403
    assert browser.post("/api/admin/test-days").status_code == 403


def test_a_code_for_a_listed_number_is_refused_if_the_number_is_removed_before_verifying(make_client):
    browser = make_client(None)
    admin_list(browser, ADMIN)
    send(browser, ADMIN)
    code = sms(browser).code_for(ADMIN)
    admin_list(browser)
    assert verify(browser, ADMIN, code).status_code == 403
    assert browser.get("/api/me").status_code == 401


def test_wrong_codes_and_the_one_a_minute_limit_apply(make_client):
    browser = make_client(None)
    admin_list(browser, ADMIN)
    send(browser, ADMIN)
    assert send(browser, ADMIN).status_code == 429
    right = sms(browser).code_for(ADMIN)
    wrong = "0000" if right != "0000" else "1111"
    assert verify(browser, ADMIN, wrong).status_code == 401
    assert verify(browser, ADMIN, right).status_code == 200


def test_trying_many_numbers_from_one_connection_is_stopped(make_client):
    browser = make_client(None)
    admin_list(browser, ADMIN)
    for i in range(10):
        assert send(browser, f"98470100{i:02d}").status_code == 403
    assert send(browser, "9847010099").status_code == 429
    assert sms(browser).sent == []


def test_a_customer_account_with_an_admin_number_becomes_that_admin(make_client):
    customer = make_client("meera")  # a customer account, with its own verified number
    mobile = customer.get("/api/me").json()["mobile"]
    assert customer.get("/api/admin/draw-days").status_code == 403
    browser = make_client(None)
    admin_list(browser, mobile)
    send(browser, mobile)
    me = verify(browser, mobile).json()
    assert (me["name"], me["role"]) == ("Meera Tester", "admin")  # the same account, now an Admin


def test_a_customer_code_for_an_unlisted_number_never_opens_the_admin_page(make_client):
    browser = make_client(None)
    admin_list(browser, ADMIN)
    browser.post("/api/auth/otp/send", json={"mobile": "9847000002"})  # the customer sign-in, a normal number
    code = sms(browser).code_for("9847000002")
    assert verify(browser, "9847000002", code).status_code == 403


def test_google_admins_are_unaffected(make_client):
    admin = make_client("admin")  # admin@example.com is on ADMIN_EMAILS
    assert admin.get("/api/admin/draw-days").status_code == 200


def test_admin_mobiles_are_read_in_any_common_format():
    assert admin_mobiles("+91 98470 00001, 919847000002,9847000003 , ,12345") == frozenset(
        {"9847000001", "9847000002", "9847000003"}
    )
