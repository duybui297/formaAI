"""Add team_invites table.

Revision ID: 0019_team_invites
Revises: 0018_api_keys
Create Date: 2026-06-07
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

# revision identifiers
revision = "0019_team_invites"
down_revision = "0018_api_keys"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "team_invites",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("workspace_owner_id", sa.String(36), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("email", sa.String(255), nullable=False),
        sa.Column("role", sa.String(32), nullable=False, server_default="member"),
        sa.Column("token", sa.String(128), nullable=False),
        sa.Column("status", sa.String(16), nullable=False, server_default="pending"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("accepted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_team_invites_workspace_owner", "team_invites", ["workspace_owner_id"])
    op.create_index("ix_team_invites_token", "team_invites", ["token"], unique=True)


def downgrade() -> None:
    op.drop_index("ix_team_invites_token", "team_invites")
    op.drop_index("ix_team_invites_workspace_owner", "team_invites")
    op.drop_table("team_invites")
