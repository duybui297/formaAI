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
    processing = "processing"   # US-3.7 AC: renamed from "running" for spec alignment
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


class FailureReason(str, enum.Enum):
    """US-3.8: Categorized failure reasons for translation jobs."""

    UNSUPPORTED_CONTENT = "unsupported_content"
    OCR_LOW_CONFIDENCE = "ocr_low_confidence"
    MODEL_TIMEOUT = "model_timeout"
    PAYMENT = "payment"
    QUOTA_EXCEEDED = "quota_exceeded"
    FEATURE_NOT_IN_PLAN = "feature_not_in_plan"
    SEGMENT_TOO_LARGE = "segment_too_large"
    TRANSLATION_ERROR = "translation_error"


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

    idempotency_key: Mapped[str | None] = mapped_column(
        String(255), nullable=True, index=True
    )

    queue_priority: Mapped[int | None] = mapped_column(Integer, nullable=True)

    # US-3.6: estimated credit cost for this job (used for refund on failure)
    estimated_credit_cost: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    # D-10: progress counters for SSE payload
    segments_done: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    segments_total: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    retry_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    error_msg: Mapped[str | None] = mapped_column(Text, nullable=True)

    # US-3.8: failure categorization with typed reasons
    failure_reason: Mapped[FailureReason | None] = mapped_column(
        String(50), nullable=True
    )
    failure_details: Mapped[dict | None] = mapped_column(JSON, nullable=True)

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
        "Segment", back_populates="job", lazy="selectin",
        cascade="all, delete-orphan",
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
        "SegmentFlag", back_populates="segment", lazy="selectin",
        passive_deletes=True,
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
# Language Catalogue (US-3.2 AC-3)
# ---------------------------------------------------------------------------


class Language(Base):
    """
    Admin-managed language catalogue — replaces the hardcoded SUPPORTED_LANGUAGES list.

    popularity_rank: lower = more popular → shown first in the dropdown.
    is_active: False hides the language from the dropdown without deleting the row.
    """

    __tablename__ = "language_catalogue"

    code: Mapped[str] = mapped_column(String(16), primary_key=True)
    name: Mapped[str] = mapped_column(String(64), nullable=False)
    qwen_code: Mapped[str] = mapped_column(String(64), nullable=False)
    is_auto_detect: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    popularity_rank: Mapped[int] = mapped_column(Integer, default=999, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)


# ---------------------------------------------------------------------------
# Chunked Upload Sessions
# ---------------------------------------------------------------------------


class UploadSessionStatus(str, enum.Enum):
    active = "active"
    completed = "completed"
    expired = "expired"
    cancelled = "cancelled"


class UploadSession(Base):
    """
    Tracks a multi-chunk file upload session.

    Flow:
      1. POST /upload/init        → create session, return upload_id + chunk_size
      2. POST /upload/{id}/chunks/{n}  → write one chunk to disk
      3. POST /upload/{id}/complete     → assemble chunks, create Job, enqueue translate_job
      4. DELETE /upload/{id}           → cancel session, delete temp chunks
    """

    __tablename__ = "upload_sessions"
    __table_args__ = (
        Index("ix_upload_sessions_user_active", "user_id", "status"),
    )

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    user_id: Mapped[str | None] = mapped_column(
        String(36),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    original_filename: Mapped[str] = mapped_column(String(512), nullable=False)
    file_size: Mapped[int] = mapped_column(Integer, nullable=False)
    chunk_size: Mapped[int] = mapped_column(Integer, nullable=False)
    total_chunks: Mapped[int] = mapped_column(Integer, nullable=False)
    # List of 0-indexed chunk numbers that have been received
    uploaded_chunks: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    # Directory where chunks are stored temporarily
    session_path: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(
        String(32),
        default=UploadSessionStatus.active.value,
        nullable=False,
    )
    # Metadata needed to create the Job once upload completes
    source_lang: Mapped[str] = mapped_column(String(64), nullable=True)
    target_lang: Mapped[str | None] = mapped_column(String(64), nullable=True)
    glossary_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    has_tracked_changes: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    tracked_changes_action: Mapped[str | None] = mapped_column(String(32), nullable=True)
    is_scanned: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    # US-3.7 AC-6: queue priority (captured at init, used at complete)
    queue_priority: Mapped[int | None] = mapped_column(Integer, nullable=True)
    # Created job_id once complete() succeeds — enables polling / SSE tracking
    job_id: Mapped[str | None] = mapped_column(String(36), nullable=True, index=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


# ---------------------------------------------------------------------------
# License Management: LicenseTier, LicenseStatus, License, LicenseActivity
# ---------------------------------------------------------------------------

class LicenseTier(str, enum.Enum):
    TRIAL = "TRIAL"
    PRO = "PRO"
    ENTERPRISE = "ENTERPRISE"


class LicenseStatus(str, enum.Enum):
    PENDING = "PENDING"
    ACTIVE = "ACTIVE"
    EXPIRED = "EXPIRED"
    SUSPENDED = "SUSPENDED"
    REVOKED = "REVOKED"


class LicenseEventType(str, enum.Enum):
    CREATED = "CREATED"
    ACTIVATED = "ACTIVATED"
    EXPIRED = "EXPIRED"
    SUSPENDED = "SUSPENDED"
    REVOKED = "REVOKED"
    EXTENDED = "EXTENDED"


class License(Base):
    """A software license issued to a customer (user)."""

    __tablename__ = "licenses"
    __table_args__ = (
        # Composite index for cron expiry scans
        Index("ix_licenses_status_expired_at", "status", "expired_at"),
    )

    # String(36) — SQLite compat for unit tests (matches repo convention)
    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    # SHA-256 hex of the raw license key — 64 chars
    key_hash: Mapped[str] = mapped_column(
        String(64), unique=True, nullable=False, index=True
    )
    tier: Mapped[LicenseTier] = mapped_column(
        SAEnum(LicenseTier), nullable=False
    )
    status: Mapped[LicenseStatus] = mapped_column(
        SAEnum(LicenseStatus), default=LicenseStatus.PENDING, nullable=False
    )
    # FK to the user who owns this license
    customer_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    max_devices: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    issued_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    activated_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    expired_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    # Caller-supplied Idempotency-Key header; repeat POSTs with the same key
    # return the existing license row without inserting a duplicate.
    idempotency_key: Mapped[str | None] = mapped_column(
        String(255), unique=True, nullable=True, index=True
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

    activities: Mapped[list["LicenseActivity"]] = relationship(
        "LicenseActivity", back_populates="license", lazy="selectin", cascade="all, delete-orphan"
    )


class LicenseActivity(Base):
    """Audit log of events on a license."""

    __tablename__ = "license_activities"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    license_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("licenses.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    event_type: Mapped[LicenseEventType] = mapped_column(
        SAEnum(LicenseEventType), nullable=False
    )
    # actor_id: nullable — system-triggered events have no human actor
    actor_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    # JSONB in Postgres; JSON in SQLite test env
    # Named event_metadata: 'metadata' is reserved by SQLAlchemy's DeclarativeBase
    event_metadata: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    license: Mapped[License] = relationship("License", back_populates="activities")


# ---------------------------------------------------------------------------
# Marketing leads (TASK-3.5)
# ---------------------------------------------------------------------------

class Lead(Base):
    """Marketing lead captured from the pricing page."""

    __tablename__ = "leads"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    email: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    plan: Mapped[str] = mapped_column(String(64), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


# ---------------------------------------------------------------------------
# US-3.8: Credits Ledger
# ---------------------------------------------------------------------------

class CreditLedger(Base):
    """
    Audit trail for credit transactions.

    Tracks every credit debit (negative) and credit refund (positive) per user.
    Positive amount = refund, Negative amount = consumption.
    """

    __tablename__ = "credits_ledger"
    __table_args__ = (
        Index("ix_credits_ledger_user_created", "user_id", "created_at"),
    )

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    user_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    job_id: Mapped[str | None] = mapped_column(
        String(36),
        ForeignKey("jobs.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )
    # Positive = refund (system→user), Negative = consumption (user→system)
    amount: Mapped[int] = mapped_column(Integer, nullable=False)
    # Reason code: translation, refund_system_failure, refund_ocr_low_confidence, etc.
    reason: Mapped[str] = mapped_column(String(64), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


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
    # TASK-3.6: soft-delete timestamp; NULL = not deleted; non-NULL = deleted
    deleted_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    # TASK-session-2026-06-07: per-user notification preferences
    notification_preferences: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    # TASK-session-2026-06-07: per-user translation defaults
    translation_defaults: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    # TASK-session-2026-06-07: team workspace — NULL means personal workspace (solo)
    workspace_id: Mapped[str | None] = mapped_column(String(36), nullable=True, index=True)
    # TASK-session-2026-06-07: avatar URL (uploaded to /static/avatars/)
    avatar_url: Mapped[str | None] = mapped_column(String(512), nullable=True)

    api_keys: Mapped[list["ApiKey"]] = relationship(
        "ApiKey", back_populates="user", lazy="selectin"
    )
    team_invites: Mapped[list["TeamInvite"]] = relationship(
        "TeamInvite", back_populates="owner", lazy="selectin"
    )


class ApiKey(Base):
    __tablename__ = "api_keys"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    user_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id"), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    key_prefix: Mapped[str] = mapped_column(String(16), nullable=False)
    key_hash: Mapped[str] = mapped_column(String(128), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    last_used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    user: Mapped[User] = relationship("User", back_populates="api_keys")


class TeamInvite(Base):
    __tablename__ = "team_invites"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    workspace_owner_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id"), nullable=False)
    email: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[str] = mapped_column(String(32), nullable=False, default="member")
    token: Mapped[str] = mapped_column(String(128), nullable=False, unique=True)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="pending")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    accepted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    owner: Mapped[User] = relationship("User", back_populates="team_invites")


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


class EmailVerificationToken(Base):
    """One-time token sent to verify a user's email after signup (US-1.1)."""

    __tablename__ = "email_verification_tokens"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    user_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    token: Mapped[str] = mapped_column(
        String(128), unique=True, nullable=False, index=True
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


# ---------------------------------------------------------------------------
# Webhook Subscriptions
# ---------------------------------------------------------------------------


class WebhookEventType(str, enum.Enum):
    translation_completed = "translation.completed"
    translation_failed = "translation.failed"


class WebhookDeliveryStatus(str, enum.Enum):
    pending = "pending"
    success = "success"
    failed = "failed"


class WebhookEndpoint(Base):
    """User-configured webhook endpoint — registers a URL to receive job events."""

    __tablename__ = "webhook_endpoints"
    __table_args__ = (
        Index("ix_webhook_endpoints_user_active", "user_id", "is_active"),
    )

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    user_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    url: Mapped[str] = mapped_column(Text, nullable=False)
    # Fernet-encrypted secret used for HMAC-SHA256 payload signing
    encrypted_secret: Mapped[str] = mapped_column(String(255), nullable=False)
    # Which job events trigger this endpoint
    events: Mapped[list] = mapped_column(JSON, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    deliveries: Mapped[list["WebhookDelivery"]] = relationship(
        "WebhookDelivery", back_populates="endpoint", lazy="selectin",
        cascade="all, delete-orphan",
    )


class WebhookDelivery(Base):
    """Audit log of each webhook delivery attempt."""

    __tablename__ = "webhook_deliveries"
    __table_args__ = (
        Index("ix_webhook_deliveries_endpoint_created", "endpoint_id", "created_at"),
    )

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    endpoint_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("webhook_endpoints.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    job_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    event_type: Mapped[WebhookEventType] = mapped_column(
        SAEnum(WebhookEventType), nullable=False
    )
    attempt: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    status: Mapped[WebhookDeliveryStatus] = mapped_column(
        SAEnum(WebhookDeliveryStatus), nullable=False
    )
    request_method: Mapped[str] = mapped_column(String(10), nullable=False)
    request_url: Mapped[str] = mapped_column(Text, nullable=False)
    request_headers: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    request_body: Mapped[str | None] = mapped_column(Text, nullable=True)
    response_status_code: Mapped[int | None] = mapped_column(Integer, nullable=True)
    response_body: Mapped[str | None] = mapped_column(Text, nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    duration_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    endpoint: Mapped[WebhookEndpoint] = relationship(
        "WebhookEndpoint", back_populates="deliveries"
    )
