import sqlalchemy as sa
from alembic import context

from app.models import Base

config = context.config


def _url() -> str:
    url = config.attributes.get("database_url")
    if url:
        return url
    from app.config import database_url

    return database_url()


def run_migrations_online() -> None:
    engine = sa.create_engine(_url(), poolclass=sa.pool.NullPool)
    with engine.connect() as connection:
        context.configure(connection=connection, target_metadata=Base.metadata, compare_type=True)
        with context.begin_transaction():
            context.run_migrations()
    engine.dispose()


run_migrations_online()
