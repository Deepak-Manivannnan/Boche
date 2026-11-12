"""Signing in or up with a mobile number: one-time codes by SMS, and the sign-up in progress.

A code is 4 digits (the SMS template's), expires after 10 minutes, allows 5 wrong tries, is used once, and is
stored salted and hashed. Sending is limited per number (one a minute while the last code is unused, five an
hour) and per connection (20 an hour), because every SMS costs money and anyone can type any number.

A sign-up in progress lives in a signed, httpOnly cookie for 30 minutes, and no account exists until the
profile is created: after "Continue with Google" it holds the Google identity; after the code is verified it
also holds the verified number."""

import base64
import hashlib
import hmac
import json
import re
import secrets
from datetime import datetime, timedelta

import sqlalchemy as sa
from sqlalchemy.orm import Session

from app.core.clock import Clock
from app.db import models as m
from app.draw.otp import OtpRefused, SmsFailed, _hash, _matches

CODE_DIGITS = 4
TTL = timedelta(minutes=10)
MAX_ATTEMPTS = 5
COOLDOWN = timedelta(seconds=60)
PER_MOBILE_PER_HOUR = 5
PER_IP_PER_HOUR = 20


def normalise_mobile(raw: str) -> str:
    """'98470 12345', '+91 98470 12345' or '919847012345' -> '9847012345'. Indian mobiles only."""
    digits = re.sub(r"\D", "", raw or "")
    if len(digits) == 12 and digits.startswith("91"):
        digits = digits[2:]
    if not re.fullmatch(r"[6-9]\d{9}", digits):
        raise OtpRefused(422, "Enter a valid 10-digit Indian mobile number")
    return digits


def mobile_taken(db: Session, mobile: str) -> bool:
    return db.scalar(sa.select(m.User.id).where(m.User.mobile == mobile)) is not None


def send_code(db: Session, mobile: str, ip: str, now: datetime, sender) -> m.LoginOtp:
    hour_ago = now - timedelta(hours=1)
    recent = db.scalars(
        sa.select(m.LoginOtp).where(m.LoginOtp.mobile == mobile, m.LoginOtp.created_at > hour_ago)
    ).all()
    last = max(recent, key=lambda o: o.created_at, default=None)
    # One a minute stops resend-spamming; a code already used (signed in) doesn't make the next sign-in wait.
    if last is not None and last.consumed_at is None and now - last.created_at < COOLDOWN:
        wait = int((COOLDOWN - (now - last.created_at)).total_seconds()) + 1
        raise OtpRefused(429, f"Wait {wait} s before asking for another code")
    if len(recent) >= PER_MOBILE_PER_HOUR:
        raise OtpRefused(429, "Too many codes for this number. Try again in an hour.")
    from_ip = db.scalar(
        sa.select(sa.func.count())
        .select_from(m.LoginOtp)
        .where(m.LoginOtp.ip == ip, m.LoginOtp.created_at > hour_ago)
    )
    if ip and from_ip >= PER_IP_PER_HOUR:
        raise OtpRefused(429, "Too many codes requested. Try again later.")

    code = f"{secrets.randbelow(10**CODE_DIGITS):0{CODE_DIGITS}d}"
    otp = m.LoginOtp(
        mobile=mobile, code_hash=_hash(code), ip=ip[:64], created_at=now, expires_at=now + TTL, attempts=0
    )
    db.add(otp)
    db.commit()
    text = f"Boche: {code} is your sign-in code. Valid 10 minutes. Do not share it with anyone."
    try:
        sender.send(mobile, code, text)
    except SmsFailed as e:  # nothing delivered: drop it so the person can ask again at once
        db.delete(otp)
        db.commit()
        raise OtpRefused(502, "The SMS could not be sent. Please try again in a moment.") from e
    return otp


def check_code(db: Session, mobile: str, code: str, now: datetime) -> None:
    """Accept the newest code sent to this number, once. A wrong code is counted and committed."""
    otp = db.scalar(
        sa.select(m.LoginOtp)
        .where(m.LoginOtp.mobile == mobile, m.LoginOtp.consumed_at.is_(None))
        .order_by(m.LoginOtp.created_at.desc(), m.LoginOtp.id.desc())
        .limit(1)
        .with_for_update()
    )
    if otp is None:
        raise OtpRefused(409, "Ask for a code first")
    if now >= otp.expires_at:
        raise OtpRefused(401, "This code has expired. Ask for a new one.")
    if otp.attempts >= MAX_ATTEMPTS:
        raise OtpRefused(429, "Too many wrong codes. Ask for a new one.")
    if not _matches(otp.code_hash, code):
        otp.attempts += 1
        db.commit()
        left = MAX_ATTEMPTS - otp.attempts
        raise OtpRefused(429 if left == 0 else 401, f"Wrong code ({left} tries left)")
    otp.consumed_at = now
    db.commit()


class PendingSignups:
    """The sign-up in progress: {"g": Google identity or absent, "m": verified mobile or absent}."""

    COOKIE = "boche_signup"
    MAX_AGE = 30 * 60

    def __init__(self, secret: str, secure: bool, clock: Clock):
        self._key = secret.encode()
        self._secure = secure
        self._clock = clock

    def _sign(self, payload: str) -> str:
        return hmac.new(self._key, f"signup|{payload}".encode(), hashlib.sha256).hexdigest()

    def issue(self, response, data: dict) -> None:
        body = base64.urlsafe_b64encode(json.dumps(data, separators=(",", ":")).encode()).decode()
        payload = f"{body}.{int(self._clock.now().timestamp())}"
        response.set_cookie(
            self.COOKIE,
            f"{payload}.{self._sign(payload)}",
            max_age=self.MAX_AGE,
            httponly=True,
            samesite="lax",
            secure=self._secure,
            path="/",
        )

    def read(self, request) -> dict | None:
        raw = request.cookies.get(self.COOKIE, "")
        try:
            body, issued, sig = raw.split(".")
            if not hmac.compare_digest(sig, self._sign(f"{body}.{issued}")):
                return None
            if not 0 <= int(self._clock.now().timestamp()) - int(issued) < self.MAX_AGE:
                return None
            data = json.loads(base64.urlsafe_b64decode(body.encode()))
        except (ValueError, json.JSONDecodeError):
            return None
        return data if isinstance(data, dict) else None

    def clear(self, response) -> None:
        response.delete_cookie(self.COOKIE, path="/", httponly=True, samesite="lax", secure=self._secure)
