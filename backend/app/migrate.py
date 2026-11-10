"""Run Alembic migrations from code (used by tests, start-up and the deploy command)."""

from pathlib import Path

from alembic import command
from alembic.config import Config

BACKEND_DIR = Path(__file__).resolve().parents[1]


def _config(url: str) -> Config:
    cfg = Config(str(BACKEND_DIR / "alembic.ini"))
    cfg.set_main_option("script_location", str(BACKEND_DIR / "migrations"))
    cfg.attributes["database_url"] = url
    return cfg


def upgrade_to_head(url: str) -> None:
    command.upgrade(_config(url), "head")


def downgrade_all(url: str) -> None:
    command.downgrade(_config(url), "base")
