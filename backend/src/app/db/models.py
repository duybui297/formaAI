from __future__ import annotations

import enum
import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, Enum as SAEnum, ForeignKey, Integer, String, Text
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
    id: Mapped[str] = mapped_column(String(16), primary_key=True)
    seq_in_job: Mapped[int] = mapped_column(Integer, nullable=False)

    job_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("jobs.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
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

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    job: Mapped[Job] = relationship("Job", back_populates="segments")
