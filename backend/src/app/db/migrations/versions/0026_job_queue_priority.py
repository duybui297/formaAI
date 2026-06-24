"""Add queue_priority to jobs table — US-3.7 AC-6.

Revision ID: 0026_job_queue_priority
Revises: 0025_job_idempotency_key
Create Date: 2026-06-22
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0026_job_queue_priority"
down_revision = "0025_job_idempotency_key"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "jobs",
        sa.Column(
            "queue_priority",
            sa.Integer(),
            nullable=True,
        ),
    )


def downgrade() -> None:
    op.drop_column("jobs", "queue_priority")
