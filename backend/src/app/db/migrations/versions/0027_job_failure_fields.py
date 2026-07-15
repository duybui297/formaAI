"""Add failure_reason and failure_details to jobs table — US-3.8.

Revision ID: 0027_job_failure_fields
Revises: 0026_job_queue_priority
Create Date: 2026-07-01
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0027_job_failure_fields"
down_revision = "0026_job_queue_priority"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "jobs",
        sa.Column(
            "failure_reason",
            sa.String(50),
            nullable=True,
        ),
    )
    op.add_column(
        "jobs",
        sa.Column(
            "failure_details",
            sa.JSON(),
            nullable=True,
        ),
    )
    # US-3.6: estimated credit cost for refund calculation
    op.add_column(
        "jobs",
        sa.Column(
            "estimated_credit_cost",
            sa.Integer(),
            nullable=False,
            server_default="0",
        ),
    )


def downgrade() -> None:
    op.drop_column("jobs", "estimated_credit_cost")
    op.drop_column("jobs", "failure_details")
    op.drop_column("jobs", "failure_reason")
