"""FastAPI application: the /api routes plus the prototype frontend on the same origin (ADR-0005)."""

import logging
import secrets
from dataclasses import replace

import sqlalchemy as sa
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy.orm import sessionmaker
from starlette.concurrency import run_in_threadpool

from app.auth.google import GoogleTokenVerifier, Sessions
from app.core.clock import Clock, SystemClock
from app.core.config import REPO_ROOT, Settings
from app.draw.drand import fetch_round
from app.draw.lifecycle import advance
from app.draw.otp import LogOtpSender, Msg91Sender
from app.draw.seals import GitHubSealPublisher

log = logging.getLogger("boche")

FRONTEND_DIR = REPO_ROOT / "frontend"


def create_app(
    settings: Settings | None = None,
    *,
    database_url: str | None = None,
    verify_google=None,
    clock: Clock | None = None,
) -> FastAPI:
    if settings is None:
        settings = Settings.from_env() if database_url is None else _minimal_settings(database_url)
    elif database_url is not None:
        settings = replace(settings, database_url=database_url)
    if len(settings.payment_secret) < 32:
        settings = replace(settings, payment_secret=secrets.token_urlsafe(48))
    clock = clock or SystemClock()

    app = FastAPI(title="Boche Lucky Draw")
    db = sa.create_engine(settings.database_url, pool_pre_ping=True, pool_recycle=280)
    app.state.settings = settings
    app.state.db = db
    app.state.sessionmaker = sessionmaker(db, expire_on_commit=False)
    app.state.clock = clock
    app.state.sessions = Sessions(settings.session_secret, settings.cookie_secure, clock)
    app.state.verify_google = verify_google or GoogleTokenVerifier(settings.google_client_id)
    app.state.seal_publisher = (
        GitHubSealPublisher(settings.seals_repo, settings.seals_token)
        if settings.seals_repo and settings.seals_token
        else None
    )
    app.state.last_advance = None
    app.state.otp_sender = (
        Msg91Sender(settings.msg91_auth_key, settings.msg91_template_id, settings.msg91_otp_variable)
        if settings.sms_mode == "msg91" and settings.msg91_auth_key and settings.msg91_template_id
        else LogOtpSender()
    )
    app.state.drand_fetch = fetch_round

    @app.middleware("http")
    async def apply_due_steps(request: Request, call_next):
        """Before any API request, apply Draw day steps that are due (at most every 15 s; /api/tick runs
        them itself). This is what closes Entries at 8 PM even if no scheduler fired."""
        path = request.url.path
        if path.startswith("/api/") and path not in ("/api/tick", "/api/health"):
            now, last = app.state.clock.now(), app.state.last_advance
            if last is None or not 0 <= (now - last).total_seconds() < 15:
                app.state.last_advance = now
                try:
                    await run_in_threadpool(advance, app.state.sessionmaker, now, app.state.seal_publisher)
                except Exception:  # a failed step must never break the request; it is retried next time
                    log.exception("applying due Draw day steps failed")
        return await call_next(request)

    @app.middleware("http")
    async def security_headers(request: Request, call_next):
        response = await call_next(request)
        # Google Identity Services needs the page origin as referrer; on plain-http localhost Google
        # asks for no-referrer-when-downgrade.
        https = request.url.scheme == "https"
        response.headers["Referrer-Policy"] = (
            "strict-origin-when-cross-origin" if https else "no-referrer-when-downgrade"
        )
        response.headers["X-Content-Type-Options"] = "nosniff"
        if request.url.path.startswith("/api/"):
            response.headers["Cache-Control"] = "no-store"
        return response

    @app.get("/api/health")
    def health():
        try:
            with db.connect() as conn:
                conn.execute(sa.text("SELECT 1"))
        except sa.exc.SQLAlchemyError:
            return JSONResponse({"status": "degraded", "database": "unreachable"}, status_code=503)
        return {"status": "ok", "database": "connected"}

    from app.auth.routes import router as auth_router
    from app.draw.routes_admin import router as admin_router
    from app.draw.routes_entries import router as entries_router
    from app.draw.routes_public import router as public_router
    from app.shop.routes import router as orders_router

    app.include_router(auth_router)
    app.include_router(orders_router)
    app.include_router(entries_router)
    app.include_router(public_router)
    app.include_router(admin_router)

    # Mounted last so every /api route above takes precedence over static files.
    app.mount("/", StaticFiles(directory=FRONTEND_DIR, html=True), name="frontend")
    return app


def _minimal_settings(database_url: str) -> Settings:
    return Settings(
        database_url=database_url,
        google_client_id="",
        session_secret="x" * 32,
        admin_emails=frozenset(),
        cookie_secure=False,
    )


def __getattr__(name: str):
    # `uvicorn app.main:app` builds the app on first access, so importing this module stays side-effect free.
    if name == "app":
        globals()["app"] = create_app()
        return globals()["app"]
    raise AttributeError(name)
