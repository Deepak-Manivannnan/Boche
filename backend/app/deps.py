"""Request-scoped helpers shared by the API routers."""

from collections.abc import Iterator

from fastapi import HTTPException, Request
from sqlalchemy.orm import Session

from app import models as m


def get_db(request: Request) -> Iterator[Session]:
    with request.app.state.sessionmaker() as session:
        yield session


def current_user(request: Request, db: Session) -> m.User:
    uid = request.app.state.sessions.user_id(request)
    user = db.get(m.User, uid) if uid is not None else None
    if user is None:
        raise HTTPException(status_code=401, detail="Not signed in")
    return user


def user_json(user: m.User) -> dict:
    return {
        "id": user.id,
        "name": user.name,
        "firstName": user.name.split(" ")[0],
        "email": user.email,
        "mobile": user.mobile,
        "role": user.role,
    }
