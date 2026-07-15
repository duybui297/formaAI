"""Create credits_ledger table — US-3.8.

Revision ID: 0028_credits_ledger
Revises: 0027_job_failure_fields
Create Date: 2026-07-01
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0028_credits_ledger"
down_revision = "0027_job_failure_fields"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "credits_ledger",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "user_id",
            sa.String(36),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "job_id",
            sa.String(36),
            sa.ForeignKey("jobs.id", ondelete="CASCADE"),
            nullable=True,
        ),
        sa.Column("amount", sa.Integer(), nullable=False),
        sa.Column("reason", sa.String(64), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )
    op.create_index("ix_credits_ledger_user_created", "credits_ledger", ["user_id", "created_at"])
    op.create_index("ix_credits_ledger_user_id", "credits_ledger", ["user_id"])
    op.create_index("ix_credits_ledger_job_id", "credits_ledger", ["job_id"])


def downgrade() -> None:
    op.drop_table("credits_ledger")
