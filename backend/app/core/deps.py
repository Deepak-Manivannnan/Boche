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


def require_admin(request: Request, db: Session) -> m.User:
    """An Admin is a signed-in user whose email is on the server's Admin list right now."""
    user = current_user(request, db)
    if user.role != "admin" or user.email not in request.app.state.settings.admin_emails:
        raise HTTPException(status_code=403, detail="Admins only")
    return user


def user_json(user: m.User) -> dict:
    return {
        "id": user.id,
        "name": user.name,
        "firstName": user.name.split(" ")[0],
        "email": user.email,
        "mobile": user.mobile,
        "picture": user.picture,
        "role": user.role,
    }
