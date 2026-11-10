"""FastAPI application: the /api routes plus the prototype frontend on the same origin (ADR-0005)."""

from pathlib import Path

import sqlalchemy as sa
from fastapi import FastAPI
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from app.config import database_url as configured_database_url

FRONTEND_DIR = Path(__file__).resolve().parents[2] / "frontend"


def create_app(database_url: str | None = None) -> FastAPI:
    app = FastAPI(title="Boche Lucky Draw")
    db = sa.create_engine(database_url or configured_database_url(), pool_pre_ping=True, pool_recycle=280)
    app.state.db = db

    @app.get("/api/health")
    def health():
        try:
            with db.connect() as conn:
                conn.execute(sa.text("SELECT 1"))
        except sa.exc.SQLAlchemyError:
            return JSONResponse({"status": "degraded", "database": "unreachable"}, status_code=503)
        return {"status": "ok", "database": "connected"}

    # Mounted last so every /api route above takes precedence over static files.
    app.mount("/", StaticFiles(directory=FRONTEND_DIR, html=True), name="frontend")
    return app


def __getattr__(name: str):
    # `uvicorn app.main:app` builds the app on first access, so importing this module stays side-effect free.
    if name == "app":
        globals()["app"] = create_app()
        return globals()["app"]
    raise AttributeError(name)
