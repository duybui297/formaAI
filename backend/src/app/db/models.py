from __future__ import annotations

import enum
import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, Enum as SAEnum, Float, ForeignKey, ForeignKeyConstraint, Index, Integer, JSON, String, Text, UniqueConstraint
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship
from sqlalchemy.sql import func


class Base(DeclarativeBase):
    pass


class JobStatus(str, enum.Enum):
    queued = "queued"
    running = "running"
    needs_review = "needs_review"
    failed = "failed"
    done = "done"


class JobStage(str, enum.Enum):
    parse = "parse"
    translate = "translate"
    reassemble = "reassemble"
    done = "done"
    failed = "failed"


class TrackedChangesAction(str, enum.Enum):
    strip = "strip"
    preserve = "preserve"


class Job(Base):
    __tablename__ = "jobs"

    # String(36) not postgresql.UUID — enables SQLite compat for unit tests
    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    status: Mapped[JobStatus] = mapped_column(
        SAEnum(JobStatus), default=JobStatus.queued, nullable=False
    )
    stage: Mapped[JobStage | None] = mapped_column(SAEnum(JobStage), nullable=True)

    source_lang: Mapped[str] = mapped_column(String(64), nullable=False)
    target_lang: Mapped[str] = mapped_column(String(64), nullable=False)
    # D-16: auto-detect via qwen-mt-turbo; persisted for UI display
    detected_lang: Mapped[str | None] = mapped_column(String(64), nullable=True)

    # docx / pdf / pptx
    input_format: Mapped[str] = mapped_column(String(16), nullable=False)
    # D-04: .data/jobs/{job_id}/source.{ext}
    input_path: Mapped[str] = mapped_column(Text, nullable=False)
    # D-04: .data/jobs/{job_id}/output.{ext} — null until reassembly complete
    output_path: Mapped[str | None] = mapped_column(Text, nullable=True)
    original_filename: Mapped[str] = mapped_column(String(512), nullable=False)

    # D-10: progress counters for SSE payload
    segments_done: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    segments_total: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    retry_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    error_msg: Mapped[str | None] = mapped_column(Text, nullable=True)

    # D-13: tracked changes detection + user choice (strip/preserve/null=none found)
    has_tracked_changes: Mapped[bool] = mapped_column(
        Boolean, default=False, nullable=False
    )
    tracked_changes_action: Mapped[TrackedChangesAction | None] = mapped_column(
        SAEnum(TrackedChangesAction), nullable=True
    )

    # Phase 2 (D-02-01): optional glossary attached to this job
    glossary_id: Mapped[str | None] = mapped_column(
        String(36),
        ForeignKey("glossaries.id", ondelete="SET NULL"),
        nullable=True,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    segments: Mapped[list[Segment]] = relationship(
        "Segment", back_populates="job", lazy="selectin"
    )


class Segment(Base):
    __tablename__ = "segments"

    # D-06: 16-char hex from sha256(source_text + structural_position)
    # Compound PK (job_id, id) — same content hash can appear in different jobs (gap-closure 02-10)
    id: Mapped[str] = mapped_column(String(16), primary_key=True)
    seq_in_job: Mapped[int] = mapped_column(Integer, nullable=False)

    job_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("jobs.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        primary_key=True,  # compound PK with id (gap-closure 02-10)
    )

    source_text: Mapped[str] = mapped_column(Text, nullable=False)
    translated_text: Mapped[str | None] = mapped_column(Text, nullable=True)

    # D-05: encodes structural location (para index / table/row/cell / header / comment)
    structural_position: Mapped[str] = mapped_column(Text, nullable=False)

    # D-14: comments are first-class Segments; author metadata preserved separately
    is_comment: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    # D-13: tracked change markers
    is_inserted: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    is_deleted: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    # run_index / run_group_size — DOCX run-level segment fields (gap-closure 02-10)
    # run_index=None for paragraph-level segments; int for run-level segments
    run_index: Mapped[int | None] = mapped_column(Integer, nullable=True)
    run_group_size: Mapped[int] = mapped_column(Integer, nullable=False, default=1)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    # Phase 2 (D-02-20): inline edits and expansion ratio tracking
    edited_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    expansion_ratio: Mapped[float | None] = mapped_column(Float, nullable=True)

    flags: Mapped[list["SegmentFlag"]] = relationship(
        "SegmentFlag", back_populates="segment", lazy="selectin"
    )

    job: Mapped[Job] = relationship("Job", back_populates="segments")


# ---------------------------------------------------------------------------
# Phase 2: Glossary + GlossaryTerm + SegmentFlag
# ---------------------------------------------------------------------------

class FlagType(str, enum.Enum):
    overflow = "overflow"
    glossary_violation = "glossary_violation"
    placeholder_mismatch = "placeholder_mismatch"
    llm_refusal = "llm_refusal"


class FlagSeverity(str, enum.Enum):
    info = "info"
    warn = "warn"
    block = "block"


class Glossary(Base):
    __tablename__ = "glossaries"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    source_lang: Mapped[str] = mapped_column(String(64), nullable=False)
    target_lang: Mapped[str] = mapped_column(String(64), nullable=False)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    terms: Mapped[list["GlossaryTerm"]] = relationship(
        "GlossaryTerm", back_populates="glossary", lazy="selectin", cascade="all, delete-orphan"
    )


class GlossaryTerm(Base):
    __tablename__ = "glossary_terms"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    glossary_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("glossaries.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    source_term: Mapped[str] = mapped_column(Text, nullable=False)
    target_term: Mapped[str] = mapped_column(Text, nullable=False)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    __table_args__ = (
        UniqueConstraint("glossary_id", "source_term", name="uq_glossary_terms_source"),
    )

    glossary: Mapped[Glossary] = relationship("Glossary", back_populates="terms")


class SegmentFlag(Base):
    __tablename__ = "segment_flags"
    __table_args__ = (
        # D-02-10: composite index for flag-count GROUP BY query
        Index("ix_segment_flags_segment_flag", "segment_id", "flag_type"),
        # gap-closure 02-10: compound FK to segments compound PK (job_id, id)
        ForeignKeyConstraint(
            ["segment_job_id", "segment_id"],
            ["segments.job_id", "segments.id"],
            ondelete="CASCADE",
            name="fk_segment_flags_segment",
        ),
    )

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    segment_id: Mapped[str] = mapped_column(String(16), nullable=False)
    segment_job_id: Mapped[str] = mapped_column(String(36), nullable=False)
    flag_type: Mapped[FlagType] = mapped_column(
        SAEnum(FlagType, native_enum=False), nullable=False
    )
    severity: Mapped[FlagSeverity] = mapped_column(
        SAEnum(FlagSeverity, native_enum=False), nullable=False
    )
    details: Mapped[dict | None] = mapped_column(JSON, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    segment: Mapped[Segment] = relationship("Segment", back_populates="flags")
