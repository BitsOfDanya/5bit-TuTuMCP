"""Create universal booking workflow table.

Revision ID: 20260819_0003
Revises: 20260819_0002
Create Date: 2026-08-19
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20260819_0003"
down_revision: str | Sequence[str] | None = "20260819_0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "bookings",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("conversation_id", sa.Uuid(), nullable=False),
        sa.Column("product_type", sa.String(length=16), nullable=False),
        sa.Column("option", sa.JSON(), nullable=False),
        sa.Column("steps", sa.JSON(), nullable=False),
        sa.Column("current_step_index", sa.Integer(), nullable=False),
        sa.Column("selections", sa.JSON(), nullable=False),
        sa.Column("travelers_count", sa.Integer(), nullable=False),
        sa.Column("confirmed", sa.Boolean(), nullable=False),
        sa.Column("checkout_url", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["conversation_id"], ["conversations.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_bookings_user_id", "bookings", ["user_id"], unique=False)
    op.create_index(
        "ix_bookings_conversation_id", "bookings", ["conversation_id"], unique=False
    )
    op.create_index(
        "ix_bookings_user_updated", "bookings", ["user_id", "updated_at"], unique=False
    )


def downgrade() -> None:
    op.drop_index("ix_bookings_user_updated", table_name="bookings")
    op.drop_index("ix_bookings_conversation_id", table_name="bookings")
    op.drop_index("ix_bookings_user_id", table_name="bookings")
    op.drop_table("bookings")
