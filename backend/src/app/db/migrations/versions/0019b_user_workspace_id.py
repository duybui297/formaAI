"""Add workspace_id to users for team workspace feature.

Revision ID: 0019b_user_workspace_id
Revises: 0019_team_invites
Create Date: 2026-06-07
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

# revision identifiers
revision = "0019b_user_workspace_id"
down_revision = "0019_team_invites"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("users", sa.Column("workspace_id", sa.String(36), nullable=True, index=True))


def downgrade() -> None:
    op.drop_column("users", "workspace_id")
