"""Phase 3: extend FlagType enum with smartart and multi_column_degraded.

NO DDL CHANGE REQUIRED.
SegmentFlag.flag_type uses native_enum=False (VARCHAR storage) per migration 0002.
New enum values are valid VARCHAR strings immediately — no ALTER TYPE or CHECK
constraint update needed. This migration exists to document the change and maintain
migration chain continuity.

Adds:
  - FlagType.smartart: PPTX SmartArt detected, write-back skipped (D-03-01)
  - FlagType.multi_column_degraded: 3+ PDF columns, flat reading order (D-03-03)
"""
from __future__ import annotations

from typing import Union

from alembic import op  # noqa: F401 (imported for migration chain; no DDL ops)

revision: str = "0004_phase3"
down_revision: Union[str, None] = "0003_segment_pk_run"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # No DDL: flag_type column uses VARCHAR via native_enum=False.
    # New FlagType values ('smartart', 'multi_column_degraded') are valid
    # immediately as VARCHAR strings. See migration 0002 for column definition.
    pass


def downgrade() -> None:
    # Cannot remove enum values from VARCHAR column without DELETE/UPDATE.
    # If downgrade needed, manually UPDATE segment_flags SET flag_type='overflow'
    # WHERE flag_type IN ('smartart', 'multi_column_degraded').
    pass
