"""Phase 4: Add OCR columns to segments; extend JobStage with ocr/compose stages.

Adds:
  - segments.confidence: Float nullable
  - segments.region_bbox: JSON nullable
  - segments.region_label: String(64) nullable
  - segments.edited_source_text: Text nullable
  - JobStage SA Enum: ADD VALUE 'ocr', ADD VALUE 'compose'
  - FlagType: no DDL needed (native_enum=False VARCHAR storage — figure_passthrough
    and ocr_page_error both fit in the existing VARCHAR(32) from 0005)
  - input_format: no DDL needed (plain String(16) — 'scanned_pdf' is valid immediately)

Threat model (T-04-01): ALTER TYPE ADD VALUE uses IF NOT EXISTS to be idempotent.
JobStage uses native PostgreSQL enum type, so ADD VALUE must run outside Alembic's
implicit transaction — op.execute("COMMIT") closes it safely.
"""
from __future__ import annotations

from typing import Union

import sqlalchemy as sa
from alembic import op

revision: str = "0006_phase4_ocr"
down_revision: Union[str, None] = "0005_widen_flag_type"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("segments", sa.Column("confidence", sa.Float(), nullable=True))
    op.add_column("segments", sa.Column("region_bbox", sa.JSON(), nullable=True))
    op.add_column("segments", sa.Column("region_label", sa.String(64), nullable=True))
    op.add_column("segments", sa.Column("edited_source_text", sa.Text(), nullable=True))

    # PostgreSQL ALTER TYPE ADD VALUE cannot run inside a transaction.
    # op.execute("COMMIT") closes Alembic's implicit transaction safely.
    # SQLite (unit tests) does not have ALTER TYPE — skip via dialect check.
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        op.execute("COMMIT")
        op.execute("ALTER TYPE jobstage ADD VALUE IF NOT EXISTS 'ocr'")
        op.execute("ALTER TYPE jobstage ADD VALUE IF NOT EXISTS 'compose'")


def downgrade() -> None:
    op.drop_column("segments", "edited_source_text")
    op.drop_column("segments", "region_label")
    op.drop_column("segments", "region_bbox")
    op.drop_column("segments", "confidence")
    # PostgreSQL does not support DROP VALUE from enum — see RESEARCH.md §migration recipe.
    # To downgrade JobStage enum values, recreate the type (complex, not worth it for PoC).
    # Document: downgrade only removes columns; ocr/compose enum values remain in DB.
