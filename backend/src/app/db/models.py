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
    ocr = "ocr"          # Phase 4: OCR stage (after parse, before translate)
    translate = "translate"
    compose = "compose"  # Phase 4: compose stage (after translate, before reassemble)
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

    # Phase 4 (D-04-23): list of 0-indexed page numbers with low OCR confidence;
    # persisted when transitioning to needs_review so banner survives page reload.
    low_confidence_pages: Mapped[list | None] = mapped_column(JSON, nullable=True)

    # Auth phase 2: owner FK — enables per-user filtering and access control.
    user_id: Mapped[str | None] = mapped_column(
        String(36),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
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

    # Phase 4 OCR columns (D-04-26)
    confidence: Mapped[float | None] = mapped_column(Float, nullable=True)
    region_bbox: Mapped[dict | None] = mapped_column(JSON, nullable=True)  # [x0,y0,x1,y1] floats in [0,1]
    region_label: Mapped[str | None] = mapped_column(String(64), nullable=True)
    edited_source_text: Mapped[str | None] = mapped_column(Text, nullable=True)

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
    smartart = "smartart"                                    # D-03-01: PPTX SmartArt detected, write-back skipped
    multi_column_degraded = "multi_column_degraded"          # D-03-03: 3+ PDF columns, flat reading order applied
    figure_passthrough = "figure_passthrough"                # Phase 4 D-04-24: image/chart block passed through untouched
    ocr_page_error = "ocr_page_error"                        # Phase 4 D-04-31: per-page OCR failure, placeholder inserted


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

    # Auth phase 2: owner FK — enables per-user filtering and access control.
    user_id: Mapped[str | None] = mapped_column(
        String(36),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
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


# ---------------------------------------------------------------------------
# Auth: User + PasswordResetToken
# ---------------------------------------------------------------------------
class User(Base):
    """Application user — email + bcrypt-hashed password."""

    __tablename__ = "users"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    email: Mapped[str] = mapped_column(
        String(255), unique=True, nullable=False, index=True
    )
    hashed_password: Mapped[str] = mapped_column(String(255), nullable=False)
    full_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    is_superuser: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    email_verified: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class PasswordResetToken(Base):
    """One-time password reset token per user."""

    __tablename__ = "password_reset_tokens"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    token: Mapped[str] = mapped_column(
        String(64), unique=True, nullable=False, index=True
    )
    user_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    used_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
