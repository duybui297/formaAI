"""Add webhook_endpoints and webhook_deliveries tables — US-9.4.

Revision ID: 022_webhook_endpoints
Revises: 0021_email_verification_tokens
Create Date: 2026-06-19
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

# revision identifiers
revision = "022_webhook_endpoints"
down_revision = "0021_email_verification_tokens"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "webhook_endpoints",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "user_id",
            sa.String(36),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("url", sa.Text, nullable=False),
        sa.Column("encrypted_secret", sa.String(255), nullable=False),
        sa.Column("events", sa.JSON, nullable=False),
        sa.Column(
            "is_active",
            sa.Boolean,
            nullable=False,
            server_default=sa.text("true"),
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )
    op.create_index(
        "ix_webhook_endpoints_user_active",
        "webhook_endpoints",
        ["user_id", "is_active"],
    )
    op.create_index(
        "ix_webhook_endpoints_user_id",
        "webhook_endpoints",
        ["user_id"],
    )

    op.create_table(
        "webhook_deliveries",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "endpoint_id",
            sa.String(36),
            sa.ForeignKey("webhook_endpoints.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("job_id", sa.String(36), nullable=False),
        sa.Column("event_type", sa.String(64), nullable=False),
        sa.Column("attempt", sa.Integer, nullable=False, server_default=sa.text("1")),
        sa.Column("status", sa.String(16), nullable=False),
        sa.Column("request_method", sa.String(10), nullable=False),
        sa.Column("request_url", sa.Text, nullable=False),
        sa.Column("request_headers", sa.JSON, nullable=True),
        sa.Column("request_body", sa.Text, nullable=True),
        sa.Column("response_status_code", sa.Integer, nullable=True),
        sa.Column("response_body", sa.Text, nullable=True),
        sa.Column("error_message", sa.Text, nullable=True),
        sa.Column("duration_ms", sa.Integer, nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )
    op.create_index(
        "ix_webhook_deliveries_endpoint_created",
        "webhook_deliveries",
        ["endpoint_id", "created_at"],
    )
    op.create_index(
        "ix_webhook_deliveries_endpoint_id",
        "webhook_deliveries",
        ["endpoint_id"],
    )
    op.create_index(
        "ix_webhook_deliveries_job_id",
        "webhook_deliveries",
        ["job_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_webhook_deliveries_job_id", "webhook_deliveries")
    op.drop_index("ix_webhook_deliveries_endpoint_id", "webhook_deliveries")
    op.drop_index("ix_webhook_deliveries_endpoint_created", "webhook_deliveries")
    op.drop_table("webhook_deliveries")

    op.drop_index("ix_webhook_endpoints_user_id", "webhook_endpoints")
    op.drop_index("ix_webhook_endpoints_user_active", "webhook_endpoints")
    op.drop_table("webhook_endpoints")
