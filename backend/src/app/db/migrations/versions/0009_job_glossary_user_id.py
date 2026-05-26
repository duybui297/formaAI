"""Auth phase 2: add user_id to jobs, add user_id to glossaries.

Adds:
  - jobs.user_id: FK to users.id, nullable (for existing rows)
  - glossaries.user_id: FK to users.id, nullable (for existing rows)

This enables per-user job/glossary filtering and access control.
"""
from __future__ import annotations

from typing import Union

import sqlalchemy as sa
from alembic import op

revision: str = "0009_job_glossary_user_id"
down_revision: Union[str, None] = "0008_auth_users"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Jobs: add user_id FK
    op.add_column(
        "jobs",
        sa.Column(
            "user_id",
            sa.String(36),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=True,
        ),
    )
    op.create_index("ix_jobs_user_id", "jobs", ["user_id"])

    # Glossaries: add user_id FK
    op.add_column(
        "glossaries",
        sa.Column(
            "user_id",
            sa.String(36),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=True,
        ),
    )
    op.create_index("ix_glossaries_user_id", "glossaries", ["user_id"])


def downgrade() -> None:
    op.drop_index("ix_glossaries_user_id", table_name="glossaries")
    op.drop_column("glossaries", "user_id")
    op.drop_index("ix_jobs_user_id", table_name="jobs")
    op.drop_column("jobs", "user_id")
