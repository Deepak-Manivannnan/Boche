"""Sign in with a mobile number: Google id and email become optional (an account can be made with a mobile
number alone), the mobile number is unique and verified, the profile has an age, and sign-in codes are kept.

Revision ID: 0005
Revises: 0004
Create Date: 2026-11-12 15:00:00
"""

import sqlalchemy as sa
from alembic import op

import app.db.models

revision = "0005"
down_revision = "0004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.alter_column("users", "google_sub", existing_type=sa.String(length=64), nullable=True)
    op.alter_column("users", "email", existing_type=sa.String(length=320), nullable=True)
    op.add_column("users", sa.Column("mobile_verified_at", app.db.models.UTCDateTime(), nullable=True))
    op.add_column("users", sa.Column("age", sa.Integer(), nullable=True))
    op.create_unique_constraint(op.f("uq_users_mobile"), "users", ["mobile"])
    op.create_table(
        "login_otps",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("mobile", sa.String(length=20), nullable=False),
        sa.Column("code_hash", sa.String(length=128), nullable=False),
        sa.Column("ip", sa.String(length=64), nullable=False),
        sa.Column("created_at", app.db.models.UTCDateTime(), nullable=False),
        sa.Column("expires_at", app.db.models.UTCDateTime(), nullable=False),
        sa.Column("attempts", sa.Integer(), nullable=False),
        sa.Column("consumed_at", app.db.models.UTCDateTime(), nullable=True),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_login_otps")),
    )
    op.create_index(op.f("ix_login_otps_mobile"), "login_otps", ["mobile"], unique=False)
    op.create_index(op.f("ix_login_otps_created_at"), "login_otps", ["created_at"], unique=False)


def downgrade() -> None:
    op.drop_table("login_otps")
    op.drop_constraint(op.f("uq_users_mobile"), "users", type_="unique")
    op.drop_column("users", "age")
    op.drop_column("users", "mobile_verified_at")
    # Going back requires every account to have a Google id and email again.
    op.alter_column("users", "email", existing_type=sa.String(length=320), nullable=False)
    op.alter_column("users", "google_sub", existing_type=sa.String(length=64), nullable=False)
