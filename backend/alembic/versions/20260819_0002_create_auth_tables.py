"""Create authentication tables.

Revision ID: 20260819_0002
Revises: 20260819_0001
Create Date: 2026-08-19
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20260819_0002"
down_revision: str | Sequence[str] | None = "20260819_0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    existing_tables = set(sa.inspect(op.get_bind()).get_table_names())

    if "user" not in existing_tables:
        op.create_table(
            "user",
            sa.Column("id", sa.String(), nullable=False),
            sa.Column("login", sa.String(length=254), nullable=False),
            sa.Column("display_name", sa.String(length=80), nullable=False),
            sa.Column("password_hash", sa.String(length=512), nullable=True),
            sa.Column("created_at", sa.Integer(), nullable=False),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index("ix_user_login", "user", ["login"], unique=True)

    if "authchallenge" not in existing_tables:
        op.create_table(
            "authchallenge",
            sa.Column("id", sa.String(), nullable=False),
            sa.Column("login", sa.String(length=254), nullable=False),
            sa.Column("code_digest", sa.String(length=64), nullable=False),
            sa.Column("expires_at", sa.Integer(), nullable=False),
            sa.Column("requested_at", sa.Integer(), nullable=False),
            sa.Column("attempts", sa.Integer(), nullable=False),
            sa.Column("consumed", sa.Boolean(), nullable=False),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index(
            "ix_authchallenge_login",
            "authchallenge",
            ["login"],
            unique=False,
        )


def downgrade() -> None:
    op.drop_index("ix_authchallenge_login", table_name="authchallenge")
    op.drop_table("authchallenge")
    op.drop_index("ix_user_login", table_name="user")
    op.drop_table("user")
