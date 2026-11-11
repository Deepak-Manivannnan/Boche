"""Delete every Test day, and the test customers' orders, cards and tickets, from DATABASE_URL.

    python scripts/delete_test_days.py

Real Draw days and real customers are never touched. Seal files already on GitHub stay there."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))

import sqlalchemy as sa  # noqa: E402
from sqlalchemy.orm import Session  # noqa: E402

from app.core.config import Settings  # noqa: E402
from app.draw.testmode import delete_test_days  # noqa: E402

if __name__ == "__main__":
    with Session(sa.create_engine(Settings.from_env().database_url)) as db:
        print(f"Deleted {delete_test_days(db)} Test days")
