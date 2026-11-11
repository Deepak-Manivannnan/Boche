"""The Founder's one-time password that lets an Admin run a Draw day's draw (ADR-0001).

The OTP decides only *when* the draw runs, never what it produces. A code is 6 digits, works for one
Draw day and one purpose, expires after 5 minutes, allows 5 wrong tries, and only the newest code is
valid. Codes are stored salted and hashed, never in plain text."""

import hashlib
import hmac
import logging
import secrets
from datetime import datetime, timedelta

import sqlalchemy as sa
from sqlalchemy.orm import Session

from app.db import models as m

log = logging.getLogger("boche.otp")

PURPOSE = "run-draw"
TTL = timedelta(minutes=5)
MAX_ATTEMPTS = 5
COOLDOWN = timedelta(seconds=60)


class OtpRefused(Exception):
    def __init__(self, status: int, detail: str):
        super().__init__(detail)
        self.status, self.detail = status, detail


class LogOtpSender:
    """Development sender: writes the SMS to the server log (Render -> Logs).

    PENDING: replace with the client's OTP service once its details arrive; the interface is send(to, text).
    """

    def send(self, to: str, text: str) -> None:
        log.warning("OTP SMS to %s: %s", to or "(FOUNDER_MOBILE not configured)", text)


def _hash(code: str, salt: str | None = None) -> str:
    salt = salt or secrets.token_hex(16)
    return f"{salt}${hashlib.sha256((salt + code).encode()).hexdigest()}"


def _matches(stored: str, code: str) -> bool:
    salt, _ = stored.split("$", 1)
    return hmac.compare_digest(stored, _hash(code, salt))


def message(day: m.DrawDay, code: str) -> str:
    return (
        f"Boche Lucky Draw {day.label}: {day.ticket_count} tickets, list {day.fingerprint[:12]}. "
        f"OTP {code} runs this draw. Valid 5 minutes. Share it only with the Boche draw admin."
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


def request_otp(db: Session, day: m.DrawDay, admin: m.User, now: datetime, sender, to: str) -> m.OtpChallenge:
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
    code = f"{secrets.randbelow(1_000_000):06d}"
    challenge = m.OtpChallenge(
        draw_day_id=day.id,
        purpose=PURPOSE,
        code_hash=_hash(code),
        requested_by=admin.id,
        created_at=now,
        expires_at=now + TTL,
        attempts=0,
    )
    db.add(challenge)
    db.commit()
    sender.send(to, message(day, code))
    challenge.plain_code = code  # in memory only, never stored
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
