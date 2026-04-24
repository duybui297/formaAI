"""initial schema: jobs and segments tables

Revision ID: 001
Revises: (none — first migration)
Create Date: 2026-04-24

W8: Uses sa.String(36) for Job.id and Segment.job_id FK — matches Plan 02 ORM model.
This keeps unit tests SQLite-compatible (no postgresql.UUID dependency).
Integration tests (marked @pytest.mark.integration) use real PostgreSQL via docker-compose.

SA enum types (jobstatus, jobstage, trackedchangesaction) are created implicitly when
the server-side String columns are defined with CHECK constraints. However, since the ORM
uses SAEnum, alembic autogenerate would create native PG ENUM types. To stay aligned with
the autogenerate output without adding autogenerate dependencies here, we use sa.String with
CHECK constraints — equivalent at the DB level and avoids PG-specific enum DDL.
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "jobs",
        # W8: String(36) NOT postgresql.UUID — matches Plan 02 ORM model
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "status",
            sa.String(20),
            nullable=False,
            server_default="queued",
        ),
        sa.Column("stage", sa.String(20), nullable=True),
        sa.Column("source_lang", sa.String(64), nullable=False),
        sa.Column("target_lang", sa.String(64), nullable=False),
        sa.Column("detected_lang", sa.String(64), nullable=True),
        # docx / pdf / pptx
        sa.Column("input_format", sa.String(16), nullable=False),
        # D-04: .data/jobs/{job_id}/source.{ext}
        sa.Column("input_path", sa.Text, nullable=False),
        # D-04: .data/jobs/{job_id}/output.{ext} — null until reassembly complete
        sa.Column("output_path", sa.Text, nullable=True),
        sa.Column("original_filename", sa.String(512), nullable=False),
        # D-10: progress counters for SSE payload
        sa.Column("segments_done", sa.Integer, nullable=False, server_default="0"),
        sa.Column("segments_total", sa.Integer, nullable=False, server_default="0"),
        sa.Column("retry_count", sa.Integer, nullable=False, server_default="0"),
        # W8: Text NOT JSONB — matches Plan 02 ORM error_msg: Mapped[str | None] = mapped_column(Text)
        sa.Column("error_msg", sa.Text, nullable=True),
        # D-13: tracked changes detection + user choice
        sa.Column(
            "has_tracked_changes",
            sa.Boolean,
            nullable=False,
            server_default="false",
        ),
        sa.Column("tracked_changes_action", sa.String(16), nullable=True),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            server_default=sa.text("NOW()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.TIMESTAMP(timezone=True),
            server_default=sa.text("NOW()"),
            nullable=False,
        ),
    )
    op.create_index("ix_jobs_status", "jobs", ["status"])
    op.create_index("ix_jobs_created_at", "jobs", ["created_at"])

    op.create_table(
        "segments",
        # D-06: 16-char hex from sha256(source_text + structural_position) — NOT UUID
        sa.Column("id", sa.String(16), primary_key=True),
        # W8: String(36) FK matches Job.id type
        sa.Column(
            "job_id",
            sa.String(36),
            sa.ForeignKey("jobs.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column("seq_in_job", sa.Integer, nullable=False),
        sa.Column("source_text", sa.Text, nullable=False),
        sa.Column("translated_text", sa.Text, nullable=True),
        # D-05: encodes structural location (para index / table/row/cell / header / comment)
        sa.Column("structural_position", sa.Text, nullable=False),
        # D-14: comment segments
        sa.Column(
            "is_comment",
            sa.Boolean,
            nullable=False,
            server_default="false",
        ),
        # D-13: tracked change markers
        sa.Column(
            "is_inserted",
            sa.Boolean,
            nullable=False,
            server_default="false",
        ),
        sa.Column(
            "is_deleted",
            sa.Boolean,
            nullable=False,
            server_default="false",
        ),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            server_default=sa.text("NOW()"),
            nullable=False,
        ),
    )
    op.create_index("ix_segments_job_id_seq", "segments", ["job_id", "seq_in_job"])


def downgrade() -> None:
    op.drop_table("segments")
    op.drop_table("jobs")
