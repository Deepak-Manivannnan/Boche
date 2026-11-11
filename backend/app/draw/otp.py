"""The Founder's one-time password that lets an Admin run a Draw day's draw (ADR-0001).

The OTP decides only *when* the draw runs, never what it produces. A code is 4 digits (the client's SMS
template says so), works for one Draw day and one purpose, expires after 10 minutes by default, allows 5
wrong tries, and only the newest code is valid. Codes are stored salted and hashed, never in plain text.

Our server makes the code; the SMS service only delivers it (MSG91 Flow API, sender SIGNTS, a DLT-approved
template with one variable for the code)."""

import hashlib
import hmac
import logging
import re
import secrets
from datetime import datetime, timedelta

import sqlalchemy as sa
from sqlalchemy.orm import Session

from app.db import models as m

log = logging.getLogger("boche.otp")

PURPOSE = "run-draw"
CODE_DIGITS = 4
TTL = timedelta(minutes=10)
MAX_ATTEMPTS = 5
COOLDOWN = timedelta(seconds=60)


class OtpRefused(Exception):
    def __init__(self, status: int, detail: str):
        super().__init__(detail)
        self.status, self.detail = status, detail


class SmsFailed(Exception):
    """The SMS service did not accept the message."""


class LogOtpSender:
    """Development sender (SMS_MODE unset): writes the OTP and its context to the server log."""

    def send(self, to: str, code: str, text: str) -> None:
        log.warning("OTP SMS to %s: %s", to or "(FOUNDER_MOBILE not configured)", text)


def indian_mobile(number: str) -> str:
    """'98XXXXXXXX', '+91 98XXX XXXXX' or '9198XXXXXXXX' -> '9198XXXXXXXX', the form MSG91 expects."""
    digits = re.sub(r"\D", "", number or "")
    if len(digits) == 10:
        digits = "91" + digits
    if len(digits) != 12 or not digits.startswith("91"):
        raise SmsFailed("FOUNDER_MOBILE is not a valid Indian mobile number")
    return digits


class Msg91Sender:
    """Delivers the code through MSG91's Flow API. Only the code goes out: the approved DLT template has
    fixed text, so the draw details stay on the admin screen. MSG91 can answer HTTP 200 with
    {"type": "error"}; only {"type": "success"} counts as sent."""

    URL = "https://control.msg91.com/api/v5/flow"

    def __init__(self, auth_key: str, template_id: str, variable: str = "OTP", http=None):
        self.auth_key, self.template_id, self.variable = auth_key, template_id, variable
        self._http = http or self._post

    def _post(self, url: str, headers: dict, body: dict) -> tuple[int, dict]:
        import requests

        res = requests.post(url, headers=headers, json=body, timeout=15)
        try:
            return res.status_code, res.json()
        except ValueError:
            return res.status_code, {}

    def send(self, to: str, code: str, text: str) -> None:
        mobile = indian_mobile(to)
        body = {"template_id": self.template_id, "recipients": [{"mobiles": mobile, self.variable: code}]}
        headers = {"authkey": self.auth_key, "accept": "application/json", "content-type": "application/json"}
        try:
            status, answer = self._http(self.URL, headers, body)
        except Exception as e:  # network failure
            raise SmsFailed(f"could not reach MSG91: {type(e).__name__}") from e
        if status != 200 or answer.get("type") != "success":
            raise SmsFailed(f"MSG91 refused the SMS (HTTP {status}): {answer.get('message', answer)}")
        log.info("OTP SMS sent to ••••••%s via MSG91", mobile[-4:])


def _hash(code: str, salt: str | None = None) -> str:
    salt = salt or secrets.token_hex(16)
    return f"{salt}${hashlib.sha256((salt + code).encode()).hexdigest()}"


def _matches(stored: str, code: str) -> bool:
    salt, _ = stored.split("$", 1)
    return hmac.compare_digest(stored, _hash(code, salt))


def message(day: m.DrawDay, code: str, ttl: timedelta = TTL) -> str:
    """The full context, written to the log by LogOtpSender. MSG91's fixed template sends only the code."""
    return (
        f"Boche Lucky Draw {day.label}: {day.ticket_count} tickets, list {day.fingerprint[:12]}. "
        f"OTP {code} runs this draw. Valid {int(ttl.total_seconds() // 60)} minutes. "
        "Share it only with the Boche draw admin."
    )


def _active(db: Session, day: m.DrawDay) -> m.OtpChallenge | None:
    return db.scalar(
        sa.select(m.OtpChallenge)
        .where(
            m.OtpChallenge.draw_day_id == day.id,
            m.OtpChallenge.purpose == PURPOSE,
            m.OtpChallenge.consumed_at.is_(None),
            m.OtpChallenge.superseded_at.is_(None),
        )
        .order_by(m.OtpChallenge.created_at.desc(), m.OtpChallenge.id.desc())
    )


def request_otp(
    db: Session, day: m.DrawDay, admin: m.User, now: datetime, sender, to: str, ttl: timedelta = TTL
) -> m.OtpChallenge:
    latest = db.scalar(
        sa.select(m.OtpChallenge)
        .where(m.OtpChallenge.draw_day_id == day.id)
        .order_by(m.OtpChallenge.created_at.desc(), m.OtpChallenge.id.desc())
    )
    if latest is not None and now - latest.created_at < COOLDOWN:
        wait = int((COOLDOWN - (now - latest.created_at)).total_seconds()) + 1
        raise OtpRefused(429, f"Wait {wait} s before requesting another OTP")
    previous = _active(db, day)
    if previous is not None:
        previous.superseded_at = now
    code = f"{secrets.randbelow(10**CODE_DIGITS):0{CODE_DIGITS}d}"
    challenge = m.OtpChallenge(
        draw_day_id=day.id,
        purpose=PURPOSE,
        code_hash=_hash(code),
        requested_by=admin.id,
        created_at=now,
        expires_at=now + ttl,
        attempts=0,
    )
    db.add(challenge)
    db.commit()
    try:
        sender.send(to, code, message(day, code, ttl))
    except SmsFailed as e:
        # Nothing was delivered: drop this code so the Admin can ask again straight away.
        log.error("OTP for %s not sent: %s", day.label, e)
        db.delete(challenge)
        db.commit()
        raise OtpRefused(502, "The OTP SMS could not be sent. Try again in a moment.") from e
    return challenge


def check_otp(db: Session, day: m.DrawDay, code: str, now: datetime) -> m.OtpChallenge:
    """Return the active challenge if `code` is right. A wrong code is counted and committed."""
    challenge = _active(db, day)
    if challenge is None:
        raise OtpRefused(409, "Request an OTP for the Founder first")
    if now >= challenge.expires_at:
        raise OtpRefused(401, "This OTP has expired; request a new one")
    if challenge.attempts >= MAX_ATTEMPTS:
        raise OtpRefused(429, "Too many wrong codes; request a new OTP")
    if not _matches(challenge.code_hash, code):
        challenge.attempts += 1
        db.commit()
        left = MAX_ATTEMPTS - challenge.attempts
        raise OtpRefused(429 if left == 0 else 401, f"Wrong OTP ({left} tries left)")
    return challenge


def active_expiry(db: Session, day: m.DrawDay, now: datetime) -> datetime | None:
    challenge = _active(db, day)
    if challenge is None or now >= challenge.expires_at or challenge.attempts >= MAX_ATTEMPTS:
        return None
    return challenge.expires_at
