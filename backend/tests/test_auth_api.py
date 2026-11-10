"""Sign-in with Google through the HTTP API. Google itself is replaced by a fake verifier."""

from datetime import UTC, datetime

import pytest
from fastapi.testclient import TestClient

from app.auth import AuthError, AuthUnavailable, GoogleIdentity
from app.clock import FixedClock
from app.config import Settings
from app.main import create_app

ARUN = GoogleIdentity(sub="g-arun", email="arun@example.com", name="Arun Mathew", picture=None)
ADMIN = GoogleIdentity(sub="g-deepak", email="deepak@example.com", name="Deepak M", picture=None)


class FakeGoogle:
    def __init__(self):
        self.tokens = {"arun-token": ARUN, "admin-token": ADMIN}
        self.down = False

    def __call__(self, credential: str) -> GoogleIdentity:
        if self.down:
            raise AuthUnavailable("google unreachable")
        if credential not in self.tokens:
            raise AuthError("bad token")
        return self.tokens[credential]


@pytest.fixture
def google():
    return FakeGoogle()


@pytest.fixture
def clock():
    return FixedClock(datetime(2026, 11, 10, 12, 0, tzinfo=UTC))


@pytest.fixture
def api(migrated_url, clean_db, google, clock):
    settings = Settings(
        database_url=migrated_url,
        google_client_id="test-client",
        session_secret="s" * 32,
        admin_emails=frozenset({"deepak@example.com"}),
        cookie_secure=False,
    )
    with TestClient(create_app(settings=settings, verify_google=google, clock=clock)) as client:
        yield client


def sign_in(api, credential="arun-token"):
    return api.post("/api/auth/google", json={"credential": credential + "x" * 10})


@pytest.fixture(autouse=True)
def _pad_tokens(google):
    # The API rejects credentials shorter than a real JWT; pad the fake ones.
    google.tokens = {k + "x" * 10: v for k, v in google.tokens.items()}


def test_a_customer_signs_in_with_google_and_gets_their_profile(api):
    res = sign_in(api)
    assert res.status_code == 200
    body = res.json()
    assert body["name"] == "Arun Mathew"
    assert body["firstName"] == "Arun"
    assert body["email"] == "arun@example.com"
    assert body["role"] == "customer"
    assert api.get("/api/me").json() == body


def test_the_session_cookie_is_http_only_and_same_site_lax(api):
    cookie = sign_in(api).headers["set-cookie"].lower()
    assert "boche_session=" in cookie
    assert "httponly" in cookie
    assert "samesite=lax" in cookie
    assert "path=/" in cookie


def test_signing_in_again_updates_the_same_customer(api, google):
    first = sign_in(api).json()
    google.tokens["arun-token" + "x" * 10] = GoogleIdentity(
        "g-arun", "arun@example.com", "Arun M. Mathew", None
    )
    again = sign_in(api).json()
    assert again["id"] == first["id"]
    assert again["name"] == "Arun M. Mathew"


def test_an_invalid_google_token_is_refused_and_no_session_is_created(api):
    res = api.post("/api/auth/google", json={"credential": "forged-token-xxxxxxxxxx"})
    assert res.status_code == 401
    assert "set-cookie" not in res.headers
    assert api.get("/api/me").status_code == 401


def test_a_missing_credential_is_rejected(api):
    assert api.post("/api/auth/google", json={}).status_code == 422


def test_google_being_down_gives_503_not_401(api, google):
    google.down = True
    assert sign_in(api).status_code == 503


def test_me_without_a_session_is_401(api):
    assert api.get("/api/me").status_code == 401


def test_a_tampered_session_cookie_is_refused(api):
    sign_in(api)
    uid, issued, sig = api.cookies.get("boche_session").split(".")
    api.cookies.clear()
    api.cookies.set("boche_session", f"{int(uid) + 1}.{issued}.{sig}")
    assert api.get("/api/me").status_code == 401
    api.cookies.clear()
    api.cookies.set("boche_session", f"{uid}.{issued}.{'0' * 64}")
    assert api.get("/api/me").status_code == 401


def test_a_session_expires_after_seven_days(api, clock):
    sign_in(api)
    clock.advance(days=7, seconds=-1)
    assert api.get("/api/me").status_code == 200
    clock.advance(seconds=2)
    assert api.get("/api/me").status_code == 401


def test_signing_out_ends_the_session(api):
    sign_in(api)
    res = api.post("/api/auth/logout")
    assert res.status_code == 204
    assert api.get("/api/me").status_code == 401


def test_an_email_on_the_admin_list_signs_in_as_admin(api):
    assert sign_in(api, "admin-token").json()["role"] == "admin"


def test_the_frontend_can_read_the_google_client_id(api):
    assert api.get("/api/config").json() == {"googleClientId": "test-client"}
