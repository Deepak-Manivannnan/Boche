"""Sign-in with Google through the HTTP API. Google itself is replaced by a fake verifier."""

from datetime import UTC, datetime

import pytest
from api_support import CodeCatcher, complete_signup, mobile_for
from fastapi.testclient import TestClient

from app.auth.google import AuthError, AuthUnavailable, GoogleIdentity
from app.core.clock import FixedClock
from app.core.config import Settings
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
        client.app.state.login_sms_sender = CodeCatcher()
        yield client


def sign_in(api, credential="arun-token"):
    """Continue with Google; a new customer then verifies a mobile number and creates the profile."""
    res = api.post("/api/auth/google", json={"credential": credential + "x" * 10})
    if res.status_code == 200 and "signup" in res.json():
        return complete_signup(api, mobile_for(credential), res.json()["signup"]["name"])
    return res


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


def test_signing_in_again_is_the_same_customer_and_keeps_their_own_name(api, google):
    first = sign_in(api).json()
    assert api.patch("/api/me", json={"name": "Arun Mathew K"}).status_code == 200
    google.tokens["arun-token" + "x" * 10] = GoogleIdentity(
        "g-arun", "arun@example.com", "Arun M. Mathew", None
    )
    again = sign_in(api).json()
    assert again["id"] == first["id"]
    assert again["name"] == "Arun Mathew K"  # the name is the customer's own; Google no longer overwrites it


ARUN_PHOTO = "https://lh3.googleusercontent.com/a/arun-photo=s96-c"
MEERA_PHOTO = "https://lh3.googleusercontent.com/a/meera-photo=s96-c"


def test_each_account_gets_its_own_google_profile_photo(api, google):
    google.tokens["arun-token" + "x" * 10] = GoogleIdentity(
        "g-arun", "arun@example.com", "Arun Mathew", ARUN_PHOTO
    )
    google.tokens["meera-token" + "x" * 10] = GoogleIdentity(
        "g-meera", "meera@example.com", "Meera K", MEERA_PHOTO
    )
    assert sign_in(api).json()["picture"] == ARUN_PHOTO
    assert api.get("/api/me").json()["picture"] == ARUN_PHOTO
    api.post("/api/auth/logout")
    assert (
        sign_in(api, "meera-token").json()["picture"] == MEERA_PHOTO
    )  # same browser, the other account's photo
    assert api.get("/api/me").json()["picture"] == MEERA_PHOTO


def test_the_photo_follows_the_google_account_at_each_sign_in(api, google):
    google.tokens["arun-token" + "x" * 10] = GoogleIdentity(
        "g-arun", "arun@example.com", "Arun Mathew", ARUN_PHOTO
    )
    sign_in(api)
    new = "https://lh3.googleusercontent.com/a/arun-new-photo=s96-c"
    google.tokens["arun-token" + "x" * 10] = GoogleIdentity("g-arun", "arun@example.com", "Arun Mathew", new)
    assert sign_in(api).json()["picture"] == new
    google.tokens["arun-token" + "x" * 10] = GoogleIdentity("g-arun", "arun@example.com", "Arun Mathew", None)
    assert sign_in(api).json()["picture"] is None  # photo removed on Google: initials again


def test_only_an_https_photo_link_is_kept(api, google):
    google.tokens["arun-token" + "x" * 10] = GoogleIdentity(
        "g-arun", "arun@example.com", "Arun Mathew", "javascript:alert(1)"
    )
    assert sign_in(api).json()["picture"] is None


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
