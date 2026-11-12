"""The daily schedule moves to 10 PM IST, and a Draw day can be `carried`: at closing time it had fewer
Tickets than Winners, so it is not sealed or drawn and its entered cards move to the next day (ADR-0011).

- Real days still taking entries were made with the 8:00 / 8:15 / 8:30 PM schedule; they move two hours
  later. (An open real day always has that standard schedule: Skip seals it, Delete restores it.)
- The status check constraint allows `carried`. Where the database does not keep check constraints (TiDB
  with them switched off), there is nothing to change.

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


SHIFT = (
    "UPDATE draw_days SET closes_at = closes_at {op} INTERVAL 2 HOUR, "
    "draw_not_before = draw_not_before {op} INTERVAL 2 HOUR, "
    "publish_not_before = publish_not_before {op} INTERVAL 2 HOUR "
    "WHERE kind = 'real' AND status = 'open'"
)


def upgrade() -> None:
    _replace(NEW)
    op.execute(SHIFT.format(op="+"))


def downgrade() -> None:
    carried = op.get_bind().scalar(sa.text("SELECT COUNT(*) FROM draw_days WHERE status = 'carried'"))
    if carried:
        raise RuntimeError(f"{carried} Draw days are 'carried'; the older schema has no such status")
    _replace(OLD)
    op.execute(SHIFT.format(op="-"))
