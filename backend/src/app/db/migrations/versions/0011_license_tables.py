"""Add licenses and license_activities tables.

Revision ID: 0011_license_tables
Revises: 0010_seed_default_user
Creates:
  - licenses: id, key_hash (UNIQUE), tier (enum), status (enum), customer_id (FK users),
              max_devices, issued_at, activated_at, expired_at, created_at, updated_at.
              Composite index (status, expired_at) for cron expiry scans.
  - license_activities: id, license_id (FK licenses), event_type (enum),
                        actor_id, metadata (JSON), created_at.
"""
from __future__ import annotations

from typing import Union

import sqlalchemy as sa
from alembic import op

revision: str = "0011_license_tables"
down_revision: Union[str, None] = "0010_seed_default_user"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # --- licenses -----------------------------------------------------------
    op.create_table(
        "licenses",
        sa.Column("id", sa.String(36), primary_key=True, nullable=False),
        sa.Column("key_hash", sa.String(64), nullable=False),
        sa.Column(
            "tier",
            sa.Enum("TRIAL", "PRO", "ENTERPRISE", name="licensetier"),
            nullable=False,
        ),
        sa.Column(
            "status",
            sa.Enum("PENDING", "ACTIVE", "EXPIRED", "SUSPENDED", "REVOKED", name="licensestatus"),
            nullable=False,
            server_default="PENDING",
        ),
        sa.Column(
            "customer_id",
            sa.String(36),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("max_devices", sa.Integer(), nullable=False, server_default="1"),
        sa.Column(
            "issued_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column("activated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("expired_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )
    op.create_unique_constraint("uq_licenses_key_hash", "licenses", ["key_hash"])
    op.create_index("ix_licenses_key_hash", "licenses", ["key_hash"], unique=True)
    op.create_index("ix_licenses_customer_id", "licenses", ["customer_id"])
    op.create_index(
        "ix_licenses_status_expired_at", "licenses", ["status", "expired_at"]
    )

    # --- license_activities -------------------------------------------------
    op.create_table(
        "license_activities",
        sa.Column("id", sa.String(36), primary_key=True, nullable=False),
        sa.Column(
            "license_id",
            sa.String(36),
            sa.ForeignKey("licenses.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "event_type",
            sa.Enum(
                "CREATED", "ACTIVATED", "EXPIRED", "SUSPENDED", "REVOKED",
                name="licenseeventtype",
            ),
            nullable=False,
        ),
        sa.Column("actor_id", sa.String(36), nullable=True),
        sa.Column("event_metadata", sa.JSON(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )
    op.create_index("ix_license_activities_license_id", "license_activities", ["license_id"])


def downgrade() -> None:
    op.drop_table("license_activities")
    op.drop_table("licenses")
    # Drop enum types (Postgres-specific; no-op on SQLite)
    op.execute("DROP TYPE IF EXISTS licenseeventtype")
    op.execute("DROP TYPE IF EXISTS licensestatus")
    op.execute("DROP TYPE IF EXISTS licensetier")
