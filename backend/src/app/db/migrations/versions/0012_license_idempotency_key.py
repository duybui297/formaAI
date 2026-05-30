"""Add idempotency_key column to licenses table.

Revision ID: 0012_license_idempotency_key
Revises: 0011_license_tables
Adds:
  - licenses.idempotency_key (String(255), nullable, unique) — caller-supplied
    Idempotency-Key header; allows repeat POSTs to return the same license
    without inserting a duplicate row.
"""
from __future__ import annotations

from typing import Union

import sqlalchemy as sa
from alembic import op

revision: str = "0012_license_idempotency_key"
down_revision: Union[str, None] = "0011_license_tables"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "licenses",
        sa.Column("idempotency_key", sa.String(255), nullable=True),
    )
    op.create_unique_constraint(
        "uq_licenses_idempotency_key", "licenses", ["idempotency_key"]
    )
    op.create_index(
        "ix_licenses_idempotency_key", "licenses", ["idempotency_key"], unique=True
    )


def downgrade() -> None:
    op.drop_index("ix_licenses_idempotency_key", table_name="licenses")
    op.drop_constraint("uq_licenses_idempotency_key", "licenses", type_="unique")
    op.drop_column("licenses", "idempotency_key")
