"""Create accepted itinerary state for Rescue and What-if.

Revision ID: 20260819_0005
Revises: 20260819_0004
Create Date: 2026-08-19
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20260819_0005"
down_revision: str | Sequence[str] | None = "20260819_0004"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "accepted_itineraries",
        sa.Column("user_id", sa.String(length=36), nullable=False),
        sa.Column("trip_spec", sa.JSON(), nullable=False),
        sa.Column("journey", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("user_id"),
    )


def downgrade() -> None:
    op.drop_table("accepted_itineraries")
