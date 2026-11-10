"""Settings come only from environment variables. A local .env file is read in development."""

import os
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
