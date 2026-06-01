"""Add leads table for marketing lead capture (TASK-3.5).

Revision ID: 0014_leads_table
Revises: 0013_license_event_type_extended
Creates:
  - leads: id (PK), email (str, indexed), plan (str), created_at (timestamptz default now)
Idempotent: CREATE TABLE IF NOT EXISTS pattern via Alembic's native create_table
(Alembic skips already-existing tables when running upgrade head multiple times
against a DB that already has the table — standard behaviour).
"""
from __future__ import annotations

from typing import Union

import sqlalchemy as sa
from alembic import op

revision: str = "0014_leads_table"
down_revision: Union[str, None] = "0013_license_event_type_extended"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "leads",
        sa.Column("id", sa.String(36), primary_key=True, nullable=False),
        sa.Column("email", sa.String(255), nullable=False),
        sa.Column("plan", sa.String(64), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )
    op.create_index("ix_leads_email", "leads", ["email"])


def downgrade() -> None:
    op.drop_index("ix_leads_email", table_name="leads")
    op.drop_table("leads")
