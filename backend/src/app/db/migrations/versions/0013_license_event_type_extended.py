"""Add EXTENDED value to licenseeventtype enum.

Revision ID: 0013_license_event_type_extended
Revises: 0012_license_idempotency_key
Adds:
  - EXTENDED value to licenseeventtype Postgres enum (idempotent via IF NOT EXISTS).
  - No-op on SQLite (VARCHAR-based enum).
"""
from __future__ import annotations

from typing import Union

from alembic import op

revision: str = "0013_license_event_type_extended"
down_revision: Union[str, None] = "0012_license_idempotency_key"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ALTER TYPE ... ADD VALUE IF NOT EXISTS is Postgres 9.1+ and idempotent.
    # SQLite uses VARCHAR for enums so this statement is skipped automatically
    # when the dialect is sqlite.
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        op.execute(
            "ALTER TYPE licenseeventtype ADD VALUE IF NOT EXISTS 'EXTENDED'"
        )


def downgrade() -> None:
    # Postgres does not support removing enum values without dropping/recreating
    # the type.  Downgrade is intentionally a no-op — EXTENDED rows would need
    # to be deleted manually before removing the value.
    pass
