"""Admins sign in on the admin page with Google or a mobile number and SMS code. Codes go only to numbers on
ADMIN_MOBILES: any other number is refused before a code is made or an SMS is sent, and admin rights are
re-checked against the lists on every request. On the customer page the same Gmail or number is an ordinary
customer with its own account and no admin rights."""

from dataclasses import replace

import sqlalchemy as sa
from api_support import complete_signup

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
    assert (me["role"], me["adminMobile"], me["name"]) == ("admin", ADMIN, "Admin")
    assert me["mobile"] is None  # an admin identity, not a customer account holding the number
    assert browser.get("/api/admin/draw-days").status_code == 200


def test_the_same_number_can_also_make_its_own_customer_account(make_client):
    admin = make_client(None)
    admin_list(admin, ADMIN)
    send(admin, ADMIN)
    admin_id = verify(admin, ADMIN).json()["id"]

    customer = make_client(None)  # the same person on the customer side, same number
    customer.post("/api/auth/otp/send", json={"mobile": ADMIN})
    step = customer.post(
        "/api/auth/otp/verify", json={"mobile": ADMIN, "code": sms(customer).code_for(ADMIN)}
    )
    assert step.json()["signup"]["step"] == "profile"  # a new customer account, not the admin identity
    me = customer.post("/api/auth/signup", json={"name": "Deepak M", "age": 30}).json()
    assert (me["mobile"], me["role"]) == (ADMIN, "customer") and me["id"] != admin_id
    assert customer.get("/api/admin/draw-days").status_code == 403  # the customer account is not an Admin
    assert admin.get("/api/admin/draw-days").status_code == 200  # the admin sign-in still is

    customer.post("/api/auth/logout")  # and next time the customer side signs in to the customer account
    customer.post("/api/auth/otp/send", json={"mobile": ADMIN})
    again = customer.post(
        "/api/auth/otp/verify", json={"mobile": ADMIN, "code": sms(customer).code_for(ADMIN)}
    )
    assert again.json()["id"] == me["id"]


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


def test_an_existing_customer_account_with_that_number_is_left_alone(make_client):
    customer = make_client("meera")  # a customer account, with its own verified number
    mine = customer.get("/api/me").json()
    browser = make_client(None)
    admin_list(browser, mine["mobile"])
    send(browser, mine["mobile"])
    admin = verify(browser, mine["mobile"]).json()
    assert admin["id"] != mine["id"] and admin["role"] == "admin"  # its own admin identity
    assert customer.get("/api/me").json() == mine  # the customer account is unchanged
    assert customer.get("/api/admin/draw-days").status_code == 403  # and gets no admin rights from its number


def test_admin_accounts_made_before_this_free_their_number(migrated_url, clean_db):
    """The live database has an "Admin" account made by the old admin mobile sign-in, holding the number as a
    customer number. The migration moves it to the admin identity; real customer accounts are untouched."""
    from alembic import command

    from app.core.migrate import _config

    cfg, engine = _config(migrated_url), sa.create_engine(migrated_url)
    command.downgrade(cfg, "0005")
    try:
        with engine.begin() as conn:
            conn.execute(
                sa.text(
                    "INSERT INTO users (name, mobile, mobile_verified_at, age, role, created_at) VALUES "
                    "('Admin', '9847000001', NOW(6), NULL, 'admin', NOW(6)), "
                    "('Meera K', '9847000002', NOW(6), 29, 'customer', NOW(6))"
                )
            )
    finally:
        command.upgrade(cfg, "head")
    with engine.connect() as conn:
        rows = conn.execute(sa.text("SELECT name, mobile, admin_mobile FROM users ORDER BY id")).all()
    engine.dispose()
    assert [tuple(r) for r in rows] == [("Admin", None, "9847000001"), ("Meera K", "9847000002", None)]


def test_a_customer_code_for_an_unlisted_number_never_opens_the_admin_page(make_client):
    browser = make_client(None)
    admin_list(browser, ADMIN)
    browser.post("/api/auth/otp/send", json={"mobile": "9847000002"})  # the customer sign-in, a normal number
    code = sms(browser).code_for("9847000002")
    assert verify(browser, "9847000002", code).status_code == 403


def test_google_admins_are_unaffected(make_client):
    admin = make_client("admin")  # admin@example.com is on ADMIN_EMAILS, signed in on the admin page
    assert admin.get("/api/admin/draw-days").status_code == 200


# ---------------------------------------------------------------- the admin Gmail works the same way


def google(client, name, admin=False):
    body = {"credential": f"{name}-token-xxxxxxxxxx", **({"admin": True} if admin else {})}
    return client.post("/api/auth/google", json=body)


def test_the_admin_gmail_on_the_customer_page_signs_up_as_an_ordinary_customer(make_client, db_engine):
    admin = make_client(None)
    admin_id = google(admin, "admin", admin=True).json()["id"]
    assert admin.get("/api/admin/draw-days").status_code == 200

    customer = make_client(None)
    step = google(customer, "admin").json()  # Continue with Google on the welcome page, same Gmail
    assert step["signup"]["step"] == "mobile"  # a customer sign-up like anyone's: number, then profile
    send_c = customer.post("/api/auth/otp/send", json={"mobile": "9847055555"})
    assert send_c.status_code == 200
    code = sms(customer).code_for("9847055555")
    customer.post("/api/auth/otp/verify", json={"mobile": "9847055555", "code": code})
    me = customer.post("/api/auth/signup", json={"name": "Admin Tester", "age": 30}).json()
    assert me["id"] != admin_id and me["role"] == "customer" and me["email"] == "admin@example.com"
    assert customer.get("/api/admin/draw-days").status_code == 403  # the customer account: no admin rights

    customer.post("/api/auth/logout")  # next time, the customer page signs in to the customer account
    assert google(customer, "admin").json()["id"] == me["id"]
    google(customer, "admin", admin=True)  # and the admin page still to the admin identity
    assert customer.get("/api/me").json()["id"] == admin_id


def test_a_customer_account_never_gets_admin_rights_from_its_email(make_client):
    customer = make_client(None)
    google(customer, "admin")  # the admin Gmail, but on the customer page
    complete_signup(customer, "9847055556", "Admin Tester")
    assert customer.get("/api/me").json()["role"] == "customer"
    assert customer.post("/api/admin/test-days").status_code == 403


def test_the_admin_page_refuses_any_other_gmail(make_client):
    res = google(make_client(None), "meera", admin=True)
    assert res.status_code == 403 and "not a Lucky Draw admin" in res.json()["detail"]


def test_the_admin_gmail_account_made_before_this_frees_its_email(migrated_url, clean_db):
    """The live admin Gmail account was made by the admin page as an ordinary account; the migration makes
    it the admin identity, so the same Gmail can sign up as a customer."""
    from alembic import command

    from app.core.migrate import _config

    cfg, engine = _config(migrated_url), sa.create_engine(migrated_url)
    command.downgrade(cfg, "0005")
    try:
        with engine.begin() as conn:
            conn.execute(
                sa.text(
                    "INSERT INTO users (google_sub, email, name, age, role, created_at) VALUES "
                    "('g-deepak', 'deepak@example.com', 'Deepak', NULL, 'admin', NOW(6)), "
                    "('g-arun', 'arun@example.com', 'Arun', 30, 'customer', NOW(6))"
                )
            )
    finally:
        command.upgrade(cfg, "head")
    with engine.connect() as conn:
        rows = conn.execute(
            sa.text("SELECT name, google_sub, email, admin_email FROM users ORDER BY id")
        ).all()
    engine.dispose()
    assert [tuple(r) for r in rows] == [
        ("Deepak", None, None, "deepak@example.com"),
        ("Arun", "g-arun", "arun@example.com", None),
    ]


def test_admin_mobiles_are_read_in_any_common_format():
    assert admin_mobiles("+91 98470 00001, 919847000002,9847000003 , ,12345") == frozenset(
        {"9847000001", "9847000002", "9847000003"}
    )
