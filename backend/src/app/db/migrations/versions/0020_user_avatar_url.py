"""Add avatar_url to users.

Revision ID: 0020_user_avatar_url
Revises: 0019b_user_workspace_id
Create Date: 2026-06-07
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

# revision identifiers
revision = "0020_user_avatar_url"
down_revision = "0019b_user_workspace_id"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column("avatar_url", sa.String(512), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("users", "avatar_url")
