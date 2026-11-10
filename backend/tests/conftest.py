"""Shared fixtures. Database tests run against TEST_DATABASE_URL (a dedicated MySQL database)."""

import os

import pytest
import sqlalchemy as sa
from sqlalchemy.orm import Session

from app.config import load_env

load_env()


@pytest.fixture(scope="session")
def migrated_url() -> str:
    url = os.environ.get("TEST_DATABASE_URL")
    if not url:
        pytest.skip("TEST_DATABASE_URL is not set")
    if not sa.make_url(url).database.endswith("_test"):
        pytest.exit(
            f"refusing to run destructive tests on {sa.make_url(url).database!r}: name must end in _test"
        )
    from app.migrate import downgrade_all, upgrade_to_head

    downgrade_all(url)
    upgrade_to_head(url)
    return url


@pytest.fixture(scope="session")
def db_engine(migrated_url):
    engine = sa.create_engine(migrated_url)
    yield engine
    engine.dispose()


def _delete_all_rows(engine) -> None:
    from app.models import Base

    with engine.begin() as conn:
        for table in reversed(Base.metadata.sorted_tables):
            conn.execute(table.delete())


@pytest.fixture
def clean_db(db_engine):
    """For tests that go through the API (which commits): start and finish with empty tables."""
    _delete_all_rows(db_engine)
    yield
    _delete_all_rows(db_engine)


@pytest.fixture
def session(db_engine):
    """A session inside a transaction that is always rolled back, so tests never leak rows."""
    with db_engine.connect() as conn:
        tx = conn.begin()
        s = Session(bind=conn, join_transaction_mode="create_savepoint")
        try:
            yield s
        finally:
            s.close()
            tx.rollback()
