"""A Draw day can be `carried`: at closing time it had fewer Tickets than Winners, so it is not sealed or
drawn and its entered cards move to the next day's draw (ADR-0011).

Only the status check constraint changes. Where the database does not keep check constraints (TiDB with
them switched off), there is nothing to change.

Revision ID: 0007
Revises: 0006
Create Date: 2026-11-12 22:00:00
"""

import sqlalchemy as sa
from alembic import op

revision = "0007"
down_revision = "0006"
branch_labels = None
depends_on = None

NAME = "ck_draw_days_draw_day_status"
OLD = ("open", "sealed", "drawn", "published")
NEW = (*OLD, "carried")


def _has_check() -> bool:
    return bool(
        op.get_bind().scalar(
            sa.text(
                "SELECT COUNT(*) FROM information_schema.TABLE_CONSTRAINTS WHERE TABLE_SCHEMA = DATABASE() "
                "AND TABLE_NAME = 'draw_days' AND CONSTRAINT_NAME = :name AND CONSTRAINT_TYPE = 'CHECK'"
            ),
            {"name": NAME},
        )
    )


def _replace(values: tuple[str, ...]) -> None:
    if not _has_check():
        return
    allowed = ", ".join(f"'{v}'" for v in values)
    op.execute(f"ALTER TABLE draw_days DROP CHECK {NAME}")
    op.execute(f"ALTER TABLE draw_days ADD CONSTRAINT {NAME} CHECK (status IN ({allowed}))")


def upgrade() -> None:
    _replace(NEW)


def downgrade() -> None:
    carried = op.get_bind().scalar(sa.text("SELECT COUNT(*) FROM draw_days WHERE status = 'carried'"))
    if carried:
        raise RuntimeError(f"{carried} Draw days are 'carried'; the older schema has no such status")
    _replace(OLD)
