"""Who is signed in: Google ID-token verification and the signed session cookie."""

import hashlib
import hmac
from dataclasses import dataclass

from google.auth import exceptions as google_exceptions
from google.auth.transport import requests as google_requests
from google.oauth2 import id_token

from app.clock import Clock


class AuthError(Exception):
    """The credential must not sign anyone in."""


class AuthUnavailable(Exception):
    """Sign-in can't be checked right now (Google unreachable, or the server isn't configured)."""


@dataclass(frozen=True)
class GoogleIdentity:
    sub: str  # Google's stable account id
    email: str  # verified, lower-case
    name: str
    picture: str | None


class GoogleTokenVerifier:
    """Checks a Google ID token: Google's signature, our client ID as audience, Google as issuer,
    not expired, and a verified email."""

    def __init__(self, client_id: str, request=None):
        self.client_id = client_id
        self._request = request or google_requests.Request()

    def __call__(self, credential: str) -> GoogleIdentity:
        if not self.client_id:
            raise AuthUnavailable("GOOGLE_CLIENT_ID is not configured")
        try:
            claims = id_token.verify_oauth2_token(
                credential, self._request, self.client_id, clock_skew_in_seconds=10
            )
        except google_exceptions.TransportError as e:
            raise AuthUnavailable(f"could not fetch Google's certificates: {e}") from e
        except (google_exceptions.GoogleAuthError, ValueError) as e:
            raise AuthError(str(e)) from e
        email = claims.get("email")
        if not email or claims.get("email_verified") is not True:
            raise AuthError("Google account has no verified email")
        email = email.strip().lower()
        return GoogleIdentity(
            sub=str(claims["sub"]),
            email=email,
            name=(claims.get("name") or email.split("@")[0]).strip()[:200],
            picture=claims.get("picture"),
        )


class Sessions:
    """A session is the cookie `<user id>.<issued at>.<HMAC-SHA256>`. httpOnly so scripts can't read it,
    SameSite=Lax so other sites can't send it with a POST, Secure when served over HTTPS."""

    COOKIE = "boche_session"
    MAX_AGE = 7 * 24 * 3600

    def __init__(self, secret: str, secure: bool, clock: Clock):
        self._key = secret.encode()
        self._secure = secure
        self._clock = clock

    def _sign(self, payload: str) -> str:
        return hmac.new(self._key, payload.encode(), hashlib.sha256).hexdigest()

    def issue(self, response, user_id: int) -> None:
        payload = f"{user_id}.{int(self._clock.now().timestamp())}"
        response.set_cookie(
            self.COOKIE,
            f"{payload}.{self._sign(payload)}",
            max_age=self.MAX_AGE,
            httponly=True,
            samesite="lax",
            secure=self._secure,
            path="/",
        )

    def user_id(self, request) -> int | None:
        raw = request.cookies.get(self.COOKIE, "")
        try:
            uid, issued, sig = raw.split(".")
            if not hmac.compare_digest(sig, self._sign(f"{uid}.{issued}")):
                return None
            age = int(self._clock.now().timestamp()) - int(issued)
        except ValueError:
            return None
        return int(uid) if 0 <= age < self.MAX_AGE else None

    def clear(self, response) -> None:
        response.delete_cookie(self.COOKIE, path="/", httponly=True, samesite="lax", secure=self._secure)
