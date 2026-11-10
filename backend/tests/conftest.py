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


from api_support import PAYMENT_SECRET  # noqa: E402


class FakeGoogle:
    """Stands in for Google: a credential "<name>-token-xxxxxxxxxx" signs in as <name>."""

    def __call__(self, credential: str):
        from app.auth import AuthError, GoogleIdentity

        name = credential.split("-token-")[0]
        if not credential.endswith("-token-xxxxxxxxxx") or not name.isalpha():
            raise AuthError("bad token")
        return GoogleIdentity(
            sub=f"g-{name}", email=f"{name}@example.com", name=f"{name.title()} Tester", picture=None
        )


@pytest.fixture
def make_client(migrated_url, clean_db):
    """make_client(name) -> a TestClient signed in as that Customer, all sharing one app and database."""
    from datetime import UTC, datetime

    from fastapi.testclient import TestClient

    from app.clock import FixedClock
    from app.config import Settings
    from app.main import create_app

    settings = Settings(
        database_url=migrated_url,
        google_client_id="test-client",
        session_secret="s" * 32,
        admin_emails=frozenset({"admin@example.com"}),
        cookie_secure=False,
        payment_secret=PAYMENT_SECRET,
    )
    clock = FixedClock(datetime(2026, 11, 10, 6, 30, tzinfo=UTC))  # 12:00 IST
    app = create_app(settings=settings, verify_google=FakeGoogle(), clock=clock)
    app.state.test_clock = clock
    clients = []

    def make(name: str | None = "arun") -> TestClient:
        client = TestClient(app)
        clients.append(client)
        if name:
            res = client.post("/api/auth/google", json={"credential": f"{name}-token-xxxxxxxxxx"})
            assert res.status_code == 200, res.text
        return client

    yield make
    for client in clients:
        client.close()


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
