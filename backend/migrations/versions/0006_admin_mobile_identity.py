"""An Admin's mobile sign-in is an admin identity of its own, apart from customer accounts.

Admin sign-ins with a mobile number used to make an ordinary account ("Admin") holding the number, so the
same number could no longer make a customer account. Those accounts (made by the admin page: role admin, no
Google account, no age) move the number to `admin_mobile`, which frees it for a customer account.

Revision ID: 0006
Revises: 0005
Create Date: 2026-11-12 19:00:00
"""

import sqlalchemy as sa
from alembic import op

revision = "0006"
down_revision = "0005"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("users", sa.Column("admin_mobile", sa.String(length=20), nullable=True))
    op.create_unique_constraint(op.f("uq_users_admin_mobile"), "users", ["admin_mobile"])
    op.execute(
        "UPDATE users SET admin_mobile = mobile, mobile = NULL, mobile_verified_at = NULL "
        "WHERE role = 'admin' AND google_sub IS NULL AND age IS NULL AND mobile IS NOT NULL"
    )


def downgrade() -> None:
    op.execute(
        "UPDATE users SET mobile = admin_mobile, mobile_verified_at = created_at "
        "WHERE admin_mobile IS NOT NULL AND mobile IS NULL"
    )
    op.drop_constraint(op.f("uq_users_admin_mobile"), "users", type_="unique")
    op.drop_column("users", "admin_mobile")
