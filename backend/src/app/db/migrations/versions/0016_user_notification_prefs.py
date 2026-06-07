"""Add notification_preferences JSONB to users.

Revision ID: 0016_user_notification_prefs
Revises: 0015_users_deleted_at
Create Date: 2026-06-07
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

# revision identifiers
revision = "0016_user_notification_prefs"
down_revision = "0015_users_deleted_at"
branch_labels = None
depends_on = None

DEFAULT_PREFS = {
    "email_job_complete": True,
    "email_job_failed": True,
    "email_license_expiry": True,
    "email_license_revoked": False,
    "email_marketing": False,
}


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column("notification_preferences", sa.JSON, nullable=True),
    )


def downgrade() -> None:
    op.drop_column("users", "notification_preferences")
