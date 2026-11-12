"""Saved delivery addresses, one set per Customer account (they used to live only in the browser).

Revision ID: 0003
Revises: 0002
Create Date: 2026-11-12 13:00:00
"""

import sqlalchemy as sa
from alembic import op

import app.db.models

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "addresses",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("user_id", sa.BigInteger(), nullable=False),
        sa.Column("label", sa.String(length=20), nullable=False),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("house", sa.String(length=200), nullable=False),
        sa.Column("street", sa.String(length=200), nullable=False),
        sa.Column("pin", sa.String(length=6), nullable=False),
        sa.Column("po", sa.String(length=100), nullable=False),
        sa.Column("district", sa.String(length=100), nullable=False),
        sa.Column("is_default", sa.Boolean(), nullable=False),
        sa.Column("created_at", app.db.models.UTCDateTime(), nullable=False),
        sa.Column("updated_at", app.db.models.UTCDateTime(), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], name=op.f("fk_addresses_user_id_users")),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_addresses")),
    )
    op.create_index(op.f("ix_addresses_user_id"), "addresses", ["user_id"], unique=False)


def downgrade() -> None:
    op.drop_table("addresses")  # drops its index with it
