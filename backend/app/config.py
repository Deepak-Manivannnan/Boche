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
    payment_secret: str = ""  # shared with the (mock) payment provider to sign confirmations
    seals_repo: str = ""  # owner/repo of the public GitHub seals repository
    seals_token: str = ""  # fine-grained token: Contents read/write on that one repository only
    founder_mobile: str = ""  # PENDING: the Founder's number for the OTP SMS (FOUNDER_MOBILE)

    @classmethod
    def from_env(cls) -> "Settings":
        load_env()
        return cls(
            database_url=database_url(),
            google_client_id=os.environ.get("GOOGLE_CLIENT_ID", "").strip(),
            session_secret=_secret("SESSION_SECRET"),
            admin_emails=frozenset(
                e.strip().lower() for e in os.environ.get("ADMIN_EMAILS", "").split(",") if e.strip()
            ),
            cookie_secure=os.environ.get("COOKIE_SECURE", "false").strip().lower() == "true",
            payment_secret=_secret("PAYMENT_WEBHOOK_SECRET"),
            seals_repo=os.environ.get("SEALS_REPO", "").strip(),
            seals_token=os.environ.get("SEALS_GITHUB_TOKEN", "").strip(),
            founder_mobile=os.environ.get("FOUNDER_MOBILE", "").strip(),
        )


def _secret(name: str) -> str:
    value = os.environ.get(name, "")
    if len(value) < 32:
        # Development fallback, valid until the server restarts. Production sets a real secret.
        print(f"WARNING: {name} missing or short; using a random per-process secret", file=sys.stderr)
        value = secrets.token_urlsafe(48)
    return value
