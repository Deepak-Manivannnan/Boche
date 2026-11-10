"""Google ID-token checks, using real RS256 signatures from a local test key instead of Google's.

The verifier runs google-auth's real verification code; only the download of Google's public
certificates is replaced, so signature, audience, issuer and expiry checks are all exercised.
"""

import datetime as dt
import json
import time

import pytest
from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.x509.oid import NameOID
from google.auth import crypt, jwt

from app.auth import AuthError, AuthUnavailable, GoogleTokenVerifier

CLIENT_ID = "1234-test.apps.googleusercontent.com"
KID = "test-key-1"


def make_key():
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "test")])
    now = dt.datetime.now(dt.UTC)
    cert = (
        x509.CertificateBuilder()
        .subject_name(name)
        .issuer_name(name)
        .public_key(key.public_key())
        .serial_number(1)
        .not_valid_before(now - dt.timedelta(days=1))
        .not_valid_after(now + dt.timedelta(days=1))
        .sign(key, hashes.SHA256())
    )
    pem_key = key.private_bytes(
        serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8, serialization.NoEncryption()
    )
    return pem_key, cert.public_bytes(serialization.Encoding.PEM).decode()


GOOGLE_KEY, GOOGLE_CERT = make_key()
OTHER_KEY, _ = make_key()


class FakeCertsResponse:
    def __init__(self, status, body):
        self.status, self.data = status, body.encode()


def certs_request(status=200):
    def request(url, method="GET", **kwargs):
        return FakeCertsResponse(status, json.dumps({KID: GOOGLE_CERT}))

    return request


def token(key=GOOGLE_KEY, **overrides) -> str:
    now = int(time.time())
    claims = {
        "iss": "https://accounts.google.com",
        "aud": CLIENT_ID,
        "sub": "1091234567890",
        "email": "arun@example.com",
        "email_verified": True,
        "name": "Arun Mathew",
        "picture": "https://lh3.googleusercontent.com/a/x",
        "iat": now,
        "exp": now + 3600,
    }
    claims.update(overrides)
    return jwt.encode(crypt.RSASigner.from_string(key, KID), claims).decode()


def verifier(status=200) -> GoogleTokenVerifier:
    return GoogleTokenVerifier(CLIENT_ID, request=certs_request(status))


def test_a_genuine_google_token_gives_the_customers_identity():
    who = verifier()(token())
    assert (who.sub, who.email, who.name) == ("1091234567890", "arun@example.com", "Arun Mathew")


def test_the_email_is_normalised_to_lower_case():
    assert verifier()(token(email="Arun@Example.COM")).email == "arun@example.com"


def test_a_token_without_a_name_falls_back_to_the_email_name():
    claims = token(name=None)
    assert verifier()(claims).name == "arun"


@pytest.mark.parametrize(
    "bad",
    [
        pytest.param({"aud": "someone-elses-app.apps.googleusercontent.com"}, id="wrong-audience"),
        pytest.param({"exp": int(time.time()) - 3600, "iat": int(time.time()) - 7200}, id="expired"),
        pytest.param({"iss": "https://evil.example"}, id="wrong-issuer"),
        pytest.param({"email_verified": False}, id="unverified-email"),
        pytest.param({"email": None}, id="no-email"),
    ],
)
def test_tokens_that_must_not_sign_anyone_in_are_refused(bad):
    with pytest.raises(AuthError):
        verifier()(token(**bad))


def test_a_token_signed_by_anyone_but_google_is_refused():
    with pytest.raises(AuthError):
        verifier()(token(key=OTHER_KEY))


def test_garbage_is_refused():
    with pytest.raises(AuthError):
        verifier()("not-a-jwt")


def test_google_being_unreachable_is_reported_separately_from_a_bad_token():
    with pytest.raises(AuthUnavailable):
        verifier(status=500)(token())


def test_a_server_without_a_client_id_refuses_to_verify():
    with pytest.raises(AuthUnavailable):
        GoogleTokenVerifier("", request=certs_request())(token())
