"""Compound PK on segments (job_id, id) + run_index / run_group_size columns.

Fixes:
  - Test 5 (blocker) — PK collision: compound PK (job_id, id) allows same segment id
    across different jobs (D-06 hash is content-addressed, not globally unique).
  - Test 4 (major) — run_index AttributeError: adds run_index (nullable) and
    run_group_size (default 1) columns needed by export reassembler.
  - SegmentFlag compound FK: drops single-column FK segment_flags.segment_id → segments.id
    and replaces with compound FK (segment_job_id, segment_id) → (segments.job_id, segments.id).
"""
from __future__ import annotations

from typing import Union

import sqlalchemy as sa
from alembic import op

revision: str = "0003_segment_pk_run"
down_revision: Union[str, None] = "0002_phase2"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ------------------------------------------------------------------
    # 1. Drop the single-column FK on segment_flags.segment_id
    #    (PostgreSQL requires FK removed before altering the referenced PK)
    # ------------------------------------------------------------------
    op.execute(
        "ALTER TABLE segment_flags DROP CONSTRAINT IF EXISTS segment_flags_segment_id_fkey"
    )

    # ------------------------------------------------------------------
    # 2. Drop the current single-column primary key on segments
    # ------------------------------------------------------------------
    op.drop_constraint("segments_pkey", "segments", type_="primary")

    # ------------------------------------------------------------------
    # 3. Create compound primary key (job_id, id)
    # ------------------------------------------------------------------
    op.create_primary_key("segments_pkey", "segments", ["job_id", "id"])

    # ------------------------------------------------------------------
    # 4. Add segment_job_id column to segment_flags (nullable first for backfill)
    # ------------------------------------------------------------------
    op.add_column(
        "segment_flags",
        sa.Column("segment_job_id", sa.String(36), nullable=True),
    )

    # Backfill segment_job_id from the segments table
    op.execute(
        """
        UPDATE segment_flags sf
        SET segment_job_id = s.job_id
        FROM segments s
        WHERE s.id = sf.segment_id
        """
    )

    # Set NOT NULL after backfill
    op.alter_column("segment_flags", "segment_job_id", nullable=False)

    # Create compound FK from segment_flags(segment_job_id, segment_id) → segments(job_id, id)
    op.create_foreign_key(
        "fk_segment_flags_segment",
        "segment_flags",
        "segments",
        ["segment_job_id", "segment_id"],
        ["job_id", "id"],
        ondelete="CASCADE",
    )

    # ------------------------------------------------------------------
    # 5. Add run_index column (nullable — None for paragraph-level segments)
    # ------------------------------------------------------------------
    op.add_column(
        "segments",
        sa.Column("run_index", sa.Integer, nullable=True),
    )

    # ------------------------------------------------------------------
    # 6. Add run_group_size column (NOT NULL, default 1)
    # ------------------------------------------------------------------
    op.add_column(
        "segments",
        sa.Column("run_group_size", sa.Integer, nullable=False, server_default="1"),
    )


def downgrade() -> None:
    # Reverse in reverse order

    # Drop run_group_size and run_index
    op.drop_column("segments", "run_group_size")
    op.drop_column("segments", "run_index")

    # Drop compound FK on segment_flags
    op.drop_constraint("fk_segment_flags_segment", "segment_flags", type_="foreignkey")

    # Drop segment_job_id column
    op.drop_column("segment_flags", "segment_job_id")

    # Drop compound PK on segments
    op.drop_constraint("segments_pkey", "segments", type_="primary")

    # Restore single-column PK on segments.id
    op.create_primary_key("segments_pkey", "segments", ["id"])

    # Restore original single-column FK on segment_flags.segment_id → segments.id
    op.create_foreign_key(
        "segment_flags_segment_id_fkey",
        "segment_flags",
        "segments",
        ["segment_id"],
        ["id"],
        ondelete="CASCADE",
    )
