"""Store the GST split (tea and logistics) on each Order, as the order screens show it.

Revision ID: 0002
Revises: 0001
Create Date: 2026-11-10 19:30:00
"""

import sqlalchemy as sa
from alembic import op

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("orders", sa.Column("tea_gst_paise", sa.Integer(), server_default="0", nullable=False))
    op.add_column(
        "orders", sa.Column("logistics_gst_paise", sa.Integer(), server_default="0", nullable=False)
    )


def downgrade() -> None:
    op.drop_column("orders", "logistics_gst_paise")
    op.drop_column("orders", "tea_gst_paise")
