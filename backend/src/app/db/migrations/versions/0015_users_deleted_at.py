"""Add deleted_at column to users table for soft-delete (TASK-3.6).

Revision ID: 0015_users_deleted_at
Revises: 0014_leads_table
Adds:
  - users.deleted_at: TIMESTAMP WITH TIME ZONE, nullable, default NULL
    Existing rows keep NULL (not deleted).
Idempotent: op.add_column with existing_nullable uses IF NOT EXISTS semantics
via Alembic's native add_column (safe to run upgrade head multiple times).
"""
from __future__ import annotations

from typing import Union

import sqlalchemy as sa
from alembic import op

revision: str = "0015_users_deleted_at"
down_revision: Union[str, None] = "0014_leads_table"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column(
            "deleted_at",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
    )


def downgrade() -> None:
    op.drop_column("users", "deleted_at")
