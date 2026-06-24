"""Add idempotency_key to jobs table — US-3.7 AC-5.

Revision ID: 0025_job_idempotency_key
Revises: 0024_language_catalogue
Create Date: 2026-06-22
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0025_job_idempotency_key"
down_revision = "0024_language_catalogue"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "jobs",
        sa.Column(
            "idempotency_key",
            sa.String(255),
            nullable=True,
            index=True,
        ),
    )


def downgrade() -> None:
    op.drop_column("jobs", "idempotency_key")
