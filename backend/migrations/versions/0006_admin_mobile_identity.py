"""Admin sign-ins are admin identities of their own, apart from customer accounts.

Signing in on the admin page (Google email on ADMIN_EMAILS, or a number on ADMIN_MOBILES) used to make or use
an ordinary account holding that email or number, so the same Google account or number could never make a
customer account. Admin identities now keep them in `admin_email` / `admin_mobile` instead.

The accounts the admin page made before (role admin, no age) move their email or number there, which frees
it for a customer account. Customer accounts (made with a profile, so they have an age) are untouched.

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
    op.add_column("users", sa.Column("admin_email", sa.String(length=320), nullable=True))
    op.add_column("users", sa.Column("admin_mobile", sa.String(length=20), nullable=True))
    op.create_unique_constraint(op.f("uq_users_admin_email"), "users", ["admin_email"])
    op.create_unique_constraint(op.f("uq_users_admin_mobile"), "users", ["admin_mobile"])
    # Made by the admin page's Google sign-in: an admin with an email but no number and no age
    op.execute(
        "UPDATE users SET admin_email = email, email = NULL, google_sub = NULL "
        "WHERE role = 'admin' AND email IS NOT NULL AND mobile IS NULL AND age IS NULL"
    )
    # Made by the admin page's mobile sign-in: an admin with a number but no Google account and no age
    op.execute(
        "UPDATE users SET admin_mobile = mobile, mobile = NULL, mobile_verified_at = NULL "
        "WHERE role = 'admin' AND google_sub IS NULL AND email IS NULL AND age IS NULL AND mobile IS NOT NULL"
    )


def downgrade() -> None:
    op.execute("UPDATE users SET email = admin_email WHERE admin_email IS NOT NULL AND email IS NULL")
    op.execute(
        "UPDATE users SET mobile = admin_mobile, mobile_verified_at = created_at "
        "WHERE admin_mobile IS NOT NULL AND mobile IS NULL"
    )
    op.drop_constraint(op.f("uq_users_admin_mobile"), "users", type_="unique")
    op.drop_constraint(op.f("uq_users_admin_email"), "users", type_="unique")
    op.drop_column("users", "admin_mobile")
    op.drop_column("users", "admin_email")
