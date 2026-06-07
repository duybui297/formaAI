"""Add translation_defaults JSONB to users.

Revision ID: 0017_user_translation_defaults
Revises: 0016_user_notification_prefs
Create Date: 2026-06-07
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

# revision identifiers
revision = "0017_user_translation_defaults"
down_revision = "0016_user_notification_prefs"
branch_labels = None
depends_on = None

DEFAULT_DEFAULTS = {
    "preferred_source_lang": None,
    "preferred_target_lang": None,
    "default_glossary_id": None,
    "auto_detect": False,
}


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column("translation_defaults", sa.JSON, nullable=True),
    )


def downgrade() -> None:
    op.drop_column("users", "translation_defaults")
