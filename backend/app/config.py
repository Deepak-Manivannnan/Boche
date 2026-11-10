"""Settings come only from environment variables. A local .env file is read in development."""

import os
import secrets
import sys
from dataclasses import dataclass
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]


def load_env() -> None:
    """Load REPO_ROOT/.env if it exists. Real environment variables always win."""
    path = REPO_ROOT / ".env"
    if not path.is_file():
        return
    from dotenv import load_dotenv

    load_dotenv(path, override=False)


def database_url() -> str:
    load_env()
    url = os.environ.get("DATABASE_URL")
    if not url:
        raise RuntimeError("DATABASE_URL is not set (see README: Run locally)")
    return url


@dataclass(frozen=True)
class Settings:
    database_url: str
    google_client_id: str  # public: it is sent to the browser
    session_secret: str  # signs session cookies; never leaves the server
    admin_emails: frozenset[str]  # lower-case emails allowed to act as Admin
    cookie_secure: bool  # True behind HTTPS (Render), False on http://localhost

    @classmethod
    def from_env(cls) -> "Settings":
        load_env()
        secret = os.environ.get("SESSION_SECRET", "")
        if len(secret) < 32:
            # Development fallback: sessions last until the server restarts. Production sets a real secret.
            print(
                "WARNING: SESSION_SECRET missing or short; using a random per-process secret", file=sys.stderr
            )
            secret = secrets.token_urlsafe(48)
        return cls(
            database_url=database_url(),
            google_client_id=os.environ.get("GOOGLE_CLIENT_ID", "").strip(),
            session_secret=secret,
            admin_emails=frozenset(
                e.strip().lower() for e in os.environ.get("ADMIN_EMAILS", "").split(",") if e.strip()
            ),
            cookie_secure=os.environ.get("COOKIE_SECURE", "false").strip().lower() == "true",
        )
