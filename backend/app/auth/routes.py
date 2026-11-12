"""Signing in and up, the current Customer, and signing out.

Two ways in:
- Google. An existing account (or an Admin) is signed in. A new Google account must first verify a mobile
  number by SMS code and then create its profile (name, age, optional address); only then is it made.
- A mobile number and SMS code. An existing number is signed in; a new number creates its profile and the
  account is made. Such an account signs in with its number only, until it connects a Google account from
  the profile.

A number belongs to one account: a Google sign-up with a number already registered is refused straight away.
Accounts made before this (Google only, no number) keep signing in with Google as they always did."""

import logging
from typing import Annotated

import sqlalchemy as sa
from fastapi import APIRouter, Depends, HTTPException, Request, Response
from pydantic import BaseModel, Field
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.auth.google import AuthError, AuthUnavailable
from app.auth.mobile import check_code, mobile_taken, normalise_mobile, send_code
from app.core.deps import current_user, get_db, role_for, user_json
from app.core.deps import is_admin as is_admin_user
from app.db import models as m
from app.draw.otp import OtpRefused
from app.shop.routes import Delivery

log = logging.getLogger("boche.auth")
router = APIRouter(prefix="/api")
Db = Annotated[Session, Depends(get_db)]
TAKEN = "This mobile number is already registered. Please use a different number."
LINKED = (
    "This Google account is already linked to another account. Please try again with a different account."
)


class GoogleSignIn(BaseModel):
    credential: str = Field(min_length=20, max_length=8192)  # the ID token from Google Identity Services
    admin: bool = False  # signing in on the staff page: only accounts in ADMIN_EMAILS may sign in there


class MobileIn(BaseModel):
    mobile: str = Field(max_length=20)


class CodeIn(MobileIn):
    code: str = Field(pattern=r"^\d{4}$")


class NewProfile(BaseModel):
    name: str = Field(min_length=2, max_length=100)
    age: int = Field(ge=18, le=120)  # a prize draw: adults only
    address: Delivery | None = None  # optional; saved as the first delivery address (Home)


class ProfileEdit(BaseModel):
    name: str = Field(min_length=2, max_length=100)


def _photo(url: str | None) -> str | None:
    return url if url and url.startswith("https://") and len(url) <= 1000 else None


def _google(request: Request, credential: str):
    try:
        return request.app.state.verify_google(credential)
    except AuthUnavailable as e:
        raise HTTPException(status_code=503, detail="Google sign-in is unavailable right now") from e
    except AuthError as e:
        raise HTTPException(status_code=401, detail="Google sign-in failed") from e


def _refused(e: OtpRefused) -> HTTPException:
    return HTTPException(status_code=e.status, detail=e.detail)


def _signed_in(request: Request, response: Response, user: m.User) -> dict:
    request.app.state.pending_signups.clear(response)
    request.app.state.sessions.issue(response, user.id)
    return user_json(user)


def _signup_state(pending: dict) -> dict:
    g = pending.get("g") or {}
    return {
        "signup": {
            "step": "profile" if pending.get("m") else "mobile",
            "via": "google" if g else "mobile",
            "name": g.get("name", ""),
            "email": g.get("email"),
            "mobile": pending.get("m"),
        }
    }


@router.get("/config")
def public_config(request: Request) -> dict:
    return {"googleClientId": request.app.state.settings.google_client_id}


@router.post("/auth/google")
def sign_in_with_google(body: GoogleSignIn, request: Request, response: Response, db: Db) -> dict:
    who = _google(request, body.credential)
    settings = request.app.state.settings
    # Match on Google's stable account id; an existing row with the same verified email is the same person.
    user = db.scalar(sa.select(m.User).where(m.User.google_sub == who.sub))
    if user is None:
        user = db.scalar(sa.select(m.User).where(m.User.email == who.email))
    # An Admin by email, or an account whose verified mobile number is on the Admin list
    is_admin = who.email in settings.admin_emails or (user is not None and is_admin_user(user, settings))
    if body.admin and not is_admin:
        # Staff page: no customer account or session is created for someone who is not an Admin.
        raise HTTPException(status_code=403, detail="This Google account is not a Lucky Draw admin")
    if user is None and not is_admin:
        # A new customer: verify a mobile number and create the profile first; no account exists yet.
        pending = {
            "g": {"sub": who.sub, "email": who.email, "name": who.name, "picture": _photo(who.picture)}
        }
        request.app.state.pending_signups.issue(response, pending)
        return _signup_state(pending)
    if user is None:
        user = m.User(google_sub=who.sub, email=who.email, name=who.name)
        db.add(user)
    # The name is the customer's own (editable in the profile), so Google no longer overwrites it.
    user.google_sub, user.email = who.sub, who.email
    user.picture = _photo(who.picture)  # refreshed so a changed Google photo shows
    # The Admin lists are server configuration, re-read at every sign-in (and every admin request).
    user.role = role_for(user, settings)
    db.commit()
    return _signed_in(request, response, user)


@router.post("/auth/otp/send")
def send_sign_in_code(body: MobileIn, request: Request, db: Db) -> dict:
    state = request.app.state
    try:
        mobile = normalise_mobile(body.mobile)
        pending = state.pending_signups.read(request) or {}
        if pending.get("g") and mobile_taken(db, mobile):
            raise OtpRefused(409, TAKEN)
        ip = request.client.host if request.client else ""
        send_code(db, mobile, ip, state.clock.now(), state.login_sms_sender)
    except OtpRefused as e:
        raise _refused(e) from e
    return {"sent": True, "mobile": mobile}


@router.post("/auth/otp/verify")
def verify_sign_in_code(body: CodeIn, request: Request, response: Response, db: Db) -> dict:
    state = request.app.state
    try:
        mobile = normalise_mobile(body.mobile)
        pending = state.pending_signups.read(request) or {}
        if pending.get("g") and mobile_taken(db, mobile):
            raise OtpRefused(409, TAKEN)
        check_code(db, mobile, body.code, state.clock.now())
    except OtpRefused as e:
        raise _refused(e) from e
    if pending.get("g"):  # Google sign-up: the number is verified, now the profile
        pending["m"] = mobile
        state.pending_signups.issue(response, pending)
        return _signup_state(pending)
    user = db.scalar(sa.select(m.User).where(m.User.mobile == mobile))
    if user is not None:  # a registered number signs in
        user.role = role_for(user, state.settings)
        db.commit()
        return _signed_in(request, response, user)
    pending = {"m": mobile}  # a new number: create the profile
    state.pending_signups.issue(response, pending)
    return _signup_state(pending)


# ---------------------------------------------------------------- Admins: mobile number + SMS code
# Codes go only to numbers on ADMIN_MOBILES. Any other number is refused before a code is made or an SMS is
# sent, and refusals from one connection are limited too, so the list can't be probed by trying numbers.

ADMIN_REFUSALS_PER_HOUR = 10


def _admin_number(request: Request, raw: str) -> str:
    state = request.app.state
    mobile = normalise_mobile(raw)
    if mobile in state.settings.admin_mobiles:
        return mobile
    ip = request.client.host if request.client else ""
    now = state.clock.now()
    recent = [t for t in state.admin_refusals.get(ip, []) if (now - t).total_seconds() < 3600]
    state.admin_refusals[ip] = recent + [now]
    log.warning("admin sign-in refused for a number not on ADMIN_MOBILES (ending %s)", mobile[-4:])
    if len(recent) >= ADMIN_REFUSALS_PER_HOUR:
        raise OtpRefused(429, "Too many attempts. Try again later.")
    raise OtpRefused(403, "This number is not an admin number")


@router.post("/auth/admin/otp/send")
def send_admin_code(body: MobileIn, request: Request, db: Db) -> dict:
    state = request.app.state
    try:
        mobile = _admin_number(request, body.mobile)  # refused before any code exists or SMS goes out
        ip = request.client.host if request.client else ""
        send_code(db, mobile, ip, state.clock.now(), state.login_sms_sender)
    except OtpRefused as e:
        raise _refused(e) from e
    return {"sent": True, "mobile": mobile}


@router.post("/auth/admin/otp/verify")
def verify_admin_code(body: CodeIn, request: Request, response: Response, db: Db) -> dict:
    state = request.app.state
    try:
        mobile = _admin_number(request, body.mobile)  # checked again: the list may have changed meanwhile
        check_code(db, mobile, body.code, state.clock.now())
    except OtpRefused as e:
        raise _refused(e) from e
    now = state.clock.now()
    user = db.scalar(sa.select(m.User).where(m.User.mobile == mobile))
    if user is None:  # the Admin's first sign-in with this number: an account for it (name editable)
        user = m.User(name="Admin", mobile=mobile, mobile_verified_at=now, created_at=now)
        db.add(user)
    user.mobile_verified_at = user.mobile_verified_at or now
    user.role = "admin"
    db.commit()
    log.warning("admin signed in with mobile number ending %s (user %s)", mobile[-4:], user.id)
    return _signed_in(request, response, user)


@router.get("/auth/signup")
def signup_in_progress(request: Request) -> dict:
    pending = request.app.state.pending_signups.read(request)
    if not pending:
        raise HTTPException(status_code=404, detail="No sign-up in progress")
    return _signup_state(pending)


@router.post("/auth/signup/cancel", status_code=204)
def cancel_signup(request: Request, response: Response) -> Response:
    request.app.state.pending_signups.clear(response)
    response.status_code = 204
    return response


@router.post("/auth/signup")
def create_profile(body: NewProfile, request: Request, response: Response, db: Db) -> dict:
    state = request.app.state
    pending = state.pending_signups.read(request) or {}
    mobile, g = pending.get("m"), pending.get("g")
    if not mobile:
        raise HTTPException(status_code=409, detail="Verify your mobile number first")
    if mobile_taken(db, mobile):
        raise HTTPException(status_code=409, detail=TAKEN)
    if g and db.scalar(
        sa.select(m.User.id).where(sa.or_(m.User.google_sub == g["sub"], m.User.email == g["email"]))
    ):
        raise HTTPException(status_code=409, detail="This Google account already has a Boche account")
    now = state.clock.now()
    user = m.User(
        google_sub=g["sub"] if g else None,
        email=g["email"] if g else None,
        picture=g.get("picture") if g else None,
        name=body.name.strip(),
        mobile=mobile,
        mobile_verified_at=now,
        age=body.age,
        role="customer",
        created_at=now,
    )
    user.role = role_for(user, state.settings)  # an Admin's own number made through sign-up is an Admin too
    db.add(user)
    try:
        db.flush()
        if body.address is not None:
            a = body.address
            db.add(
                m.Address(
                    user_id=user.id,
                    label="Home",
                    name=a.name.strip(),
                    house=a.house.strip(),
                    street=a.street.strip(),
                    pin=a.pin,
                    po=a.po.strip(),
                    district=a.district.strip(),
                    is_default=True,
                    created_at=now,
                    updated_at=now,
                )
            )
        db.commit()
    except IntegrityError as e:  # the same number or Google account was registered a moment ago
        db.rollback()
        raise HTTPException(status_code=409, detail=TAKEN) from e
    return _signed_in(request, response, user)


@router.get("/me")
def me(request: Request, db: Db) -> dict:
    return user_json(current_user(request, db))


@router.patch("/me")
def edit_profile(body: ProfileEdit, request: Request, db: Db) -> dict:
    user = current_user(request, db)
    user.name = body.name.strip()
    db.commit()
    return user_json(user)


@router.post("/me/google")
def connect_google(body: GoogleSignIn, request: Request, db: Db) -> dict:
    """An account made with a mobile number connects a Google account; then either can sign in."""
    user = current_user(request, db)
    if user.google_sub:
        raise HTTPException(status_code=409, detail="A Google account is already connected")
    who = _google(request, body.credential)
    if db.scalar(sa.select(m.User.id).where(sa.or_(m.User.google_sub == who.sub, m.User.email == who.email))):
        raise HTTPException(status_code=409, detail=LINKED)  # blocked: nothing is changed on either account
    user.google_sub, user.email, user.picture = who.sub, who.email, _photo(who.picture)
    db.commit()
    return user_json(user)


@router.post("/auth/logout", status_code=204)
def sign_out(request: Request, response: Response) -> Response:
    request.app.state.sessions.clear(response)
    request.app.state.pending_signups.clear(response)
    response.status_code = 204
    return response
