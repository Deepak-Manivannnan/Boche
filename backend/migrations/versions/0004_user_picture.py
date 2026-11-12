"""Each account's Google profile photo (its URL), refreshed at every sign-in.

Revision ID: 0004
Revises: 0003
Create Date: 2026-11-12 14:00:00
"""

import sqlalchemy as sa
from alembic import op

revision = "0004"
down_revision = "0003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("users", sa.Column("picture", sa.String(length=1000), nullable=True))


def downgrade() -> None:
    op.drop_column("users", "picture")
