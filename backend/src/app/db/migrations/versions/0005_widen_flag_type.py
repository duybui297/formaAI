"""Phase 3 hotfix: widen segment_flags.flag_type from VARCHAR(20) to VARCHAR(32).

Migration 0004 documented the FlagType enum extension but skipped DDL on the
incorrect assumption that VARCHAR storage was open-ended. SQLAlchemy's
`SAEnum(..., native_enum=False)` actually sizes the VARCHAR to the longest
enum value at table-create time. Phase 1+2 longest value was
`placeholder_mismatch` (20 chars) → column = VARCHAR(20). Phase 3 added
`multi_column_degraded` (21 chars), which the existing column cannot store —
inserts fail with `StringDataRightTruncationError` from asyncpg.

Widen the column to VARCHAR(32) for headroom against future enum values.
"""
from __future__ import annotations

from typing import Union

import sqlalchemy as sa
from alembic import op

revision: str = "0005_widen_flag_type"
down_revision: Union[str, None] = "0004_phase3"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.alter_column(
        "segment_flags",
        "flag_type",
        existing_type=sa.String(length=20),
        type_=sa.String(length=32),
        existing_nullable=False,
    )


def downgrade() -> None:
    # Truncate values longer than 20 chars before narrowing, otherwise the
    # ALTER will fail. multi_column_degraded → overflow is the safest fallback.
    op.execute(
        "UPDATE segment_flags "
        "SET flag_type = 'overflow' "
        "WHERE length(flag_type) > 20"
    )
    op.alter_column(
        "segment_flags",
        "flag_type",
        existing_type=sa.String(length=32),
        type_=sa.String(length=20),
        existing_nullable=False,
    )
