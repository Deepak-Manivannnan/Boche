"""Request-scoped helpers shared by the API routers."""

from collections.abc import Iterator

from fastapi import HTTPException, Request
from sqlalchemy.orm import Session

from app.db import models as m


def get_db(request: Request) -> Iterator[Session]:
    with request.app.state.sessionmaker() as session:
        yield session


def current_user(request: Request, db: Session) -> m.User:
    uid = request.app.state.sessions.user_id(request)
    user = db.get(m.User, uid) if uid is not None else None
    if user is None:
        raise HTTPException(status_code=401, detail="Not signed in")
    return user


def is_admin(user: m.User, settings) -> bool:
    """On the server's Admin lists right now: the Google email in ADMIN_EMAILS, or the admin identity's
    number (made by signing in on the admin page) in ADMIN_MOBILES. A customer account never becomes an
    Admin through its own mobile number. Re-read on every request, so removal from a list ends access."""
    by_email = user.email is not None and user.email in settings.admin_emails
    by_mobile = user.admin_mobile is not None and user.admin_mobile in settings.admin_mobiles
    return by_email or by_mobile


def role_for(user: m.User, settings) -> str:
    return "admin" if is_admin(user, settings) else "customer"


def require_admin(request: Request, db: Session) -> m.User:
    """An Admin is a signed-in user who is on the server's Admin lists right now."""
    user = current_user(request, db)
    if user.role != "admin" or not is_admin(user, request.app.state.settings):
        raise HTTPException(status_code=403, detail="Admins only")
    return user


def user_json(user: m.User) -> dict:
    return {
        "id": user.id,
        "name": user.name,
        "firstName": user.name.split(" ")[0],
        "email": user.email,
        "mobile": user.mobile,
        "adminMobile": user.admin_mobile,  # set only on an Admin's own mobile sign-in identity
        "age": user.age,
        "hasGoogle": bool(user.google_sub),  # false: signs in with the mobile number only
        "picture": user.picture,
        "role": user.role,
    }
