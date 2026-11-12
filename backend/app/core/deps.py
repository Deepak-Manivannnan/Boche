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
    """An admin identity (made by signing in on the admin page) whose email is on ADMIN_EMAILS or whose
    number is on ADMIN_MOBILES, right now. A customer account never becomes an Admin through its own email
    or number. Re-read on every request, so removal from a list ends access."""
    by_email = user.admin_email is not None and user.admin_email in settings.admin_emails
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
        "adminEmail": user.admin_email,  # set only on an admin identity (admin page, Google)
        "adminMobile": user.admin_mobile,  # set only on an admin identity (admin page, mobile)
        "age": user.age,
        "hasGoogle": bool(user.google_sub),  # false: signs in with the mobile number only
        "picture": user.picture,
        "role": user.role,
    }
