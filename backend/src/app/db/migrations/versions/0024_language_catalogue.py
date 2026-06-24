"""Add language_catalogue table for admin-managed language list — US-3.2 AC-3.

Revision ID: 0024_language_catalogue
Revises: 0023_upload_sessions
Create Date: 2026-06-22
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0024_language_catalogue"
down_revision = "0023_upload_sessions"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "language_catalogue",
        sa.Column("code", sa.String(16), primary_key=True),
        sa.Column("name", sa.String(64), nullable=False),
        sa.Column("qwen_code", sa.String(64), nullable=False),
        sa.Column("is_auto_detect", sa.Boolean(), nullable=False, server_default="0"),
        sa.Column("popularity_rank", sa.Integer(), nullable=False, server_default="999"),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="1"),
    )
    op.create_index(
        "ix_language_catalogue_popularity",
        "language_catalogue",
        ["popularity_rank"],
    )


def downgrade() -> None:
    op.drop_index("ix_language_catalogue_popularity", table_name="language_catalogue")
    op.drop_table("language_catalogue")
