"""Add upload_sessions table for chunked resumable uploads — US-3.1 AC-4.

Revision ID: 0023_upload_sessions
Revises: 022_webhook_endpoints
Create Date: 2026-06-22
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0023_upload_sessions"
down_revision = "022_webhook_endpoints"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "upload_sessions",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "user_id",
            sa.String(36),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column("original_filename", sa.String(512), nullable=False),
        sa.Column("file_size", sa.Integer(), nullable=False),
        sa.Column("chunk_size", sa.Integer(), nullable=False),
        sa.Column("total_chunks", sa.Integer(), nullable=False),
        sa.Column(
            "uploaded_chunks",
            sa.JSON(),
            nullable=False,
            default=list,
        ),
        sa.Column("session_path", sa.Text(), nullable=False),
        sa.Column(
            "status",
            sa.String(32),
            nullable=False,
            server_default="active",
        ),
        sa.Column("source_lang", sa.String(64), nullable=True),
        sa.Column("target_lang", sa.String(64), nullable=True),
        sa.Column("glossary_id", sa.String(36), nullable=True),
        sa.Column(
            "has_tracked_changes",
            sa.Boolean(),
            nullable=False,
            server_default="0",
        ),
        sa.Column("tracked_changes_action", sa.String(32), nullable=True),
        sa.Column(
            "is_scanned",
            sa.Boolean(),
            nullable=False,
            server_default="0",
        ),
        sa.Column("queue_priority", sa.Integer(), nullable=True),
        sa.Column("job_id", sa.String(36), nullable=True, index=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )
    op.create_index(
        "ix_upload_sessions_user_active",
        "upload_sessions",
        ["user_id", "status"],
    )


def downgrade() -> None:
    op.drop_index("ix_upload_sessions_user_active", table_name="upload_sessions")
    op.drop_table("upload_sessions")
