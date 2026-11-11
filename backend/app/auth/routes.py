"""Sign in with Google, the current Customer, and sign out."""

from typing import Annotated

import sqlalchemy as sa
from fastapi import APIRouter, Depends, HTTPException, Request, Response
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.auth.google import AuthError, AuthUnavailable
from app.core.deps import current_user, get_db, user_json
from app.db import models as m

router = APIRouter(prefix="/api")
Db = Annotated[Session, Depends(get_db)]


class GoogleSignIn(BaseModel):
    credential: str = Field(min_length=20, max_length=8192)  # the ID token from Google Identity Services
    admin: bool = False  # signing in on the staff page: only accounts in ADMIN_EMAILS may sign in there


@router.get("/config")
def public_config(request: Request) -> dict:
    return {"googleClientId": request.app.state.settings.google_client_id}


@router.post("/auth/google")
def sign_in_with_google(body: GoogleSignIn, request: Request, response: Response, db: Db) -> dict:
    try:
        who = request.app.state.verify_google(body.credential)
    except AuthUnavailable as e:
        raise HTTPException(status_code=503, detail="Google sign-in is unavailable right now") from e
    except AuthError as e:
        raise HTTPException(status_code=401, detail="Google sign-in failed") from e

    if body.admin and who.email not in request.app.state.settings.admin_emails:
        # Staff page: no customer account or session is created for someone who is not an Admin.
        raise HTTPException(status_code=403, detail="This Google account is not a Lucky Draw admin")

    # Match on Google's stable account id; an existing row with the same verified email is the same person.
    user = db.scalar(sa.select(m.User).where(m.User.google_sub == who.sub))
    if user is None:
        user = db.scalar(sa.select(m.User).where(m.User.email == who.email))
    if user is None:
        user = m.User(google_sub=who.sub, email=who.email, name=who.name)
        db.add(user)
    user.google_sub, user.email, user.name = who.sub, who.email, who.name
    # The Admin list is server configuration, re-read at every sign-in so removal takes effect.
    user.role = "admin" if who.email in request.app.state.settings.admin_emails else "customer"
    db.commit()

    request.app.state.sessions.issue(response, user.id)
    return user_json(user)


@router.get("/me")
def me(request: Request, db: Db) -> dict:
    return user_json(current_user(request, db))


@router.post("/auth/logout", status_code=204)
def sign_out(request: Request, response: Response) -> Response:
    request.app.state.sessions.clear(response)
    response.status_code = 204
    return response
