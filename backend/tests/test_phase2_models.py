"""Phase 2 ORM model tests (TDD RED → GREEN).

Tests:
  - FlagType and FlagSeverity enums importable
  - Glossary, GlossaryTerm, SegmentFlag models importable
  - Job.glossary_id column exists (nullable FK)
  - Segment.edited_text and Segment.expansion_ratio columns exist
  - SegmentFlag uses native_enum=False on SAEnum columns
  - Basic SQLite round-trip for new models
"""
from __future__ import annotations

import pytest
import pytest_asyncio


# ---------------------------------------------------------------------------
# Import tests — fail immediately if model additions are missing
# ---------------------------------------------------------------------------


def test_flag_type_importable() -> None:
    from app.db.models import FlagType

    assert FlagType.overflow == "overflow"
    assert FlagType.glossary_violation == "glossary_violation"
    assert FlagType.placeholder_mismatch == "placeholder_mismatch"
    assert FlagType.llm_refusal == "llm_refusal"


def test_flag_severity_importable() -> None:
    from app.db.models import FlagSeverity

    assert FlagSeverity.info == "info"
    assert FlagSeverity.warn == "warn"
    assert FlagSeverity.block == "block"


def test_new_models_importable() -> None:
    from app.db.models import Glossary, GlossaryTerm, SegmentFlag  # noqa: F401


def test_job_has_glossary_id_column() -> None:
    from sqlalchemy import inspect as sa_inspect

    from app.db.models import Job

    mapper = sa_inspect(Job)
    col_names = [c.key for c in mapper.columns]
    assert "glossary_id" in col_names, f"glossary_id missing from Job columns: {col_names}"


def test_segment_has_edited_text_column() -> None:
    from sqlalchemy import inspect as sa_inspect

    from app.db.models import Segment

    mapper = sa_inspect(Segment)
    col_names = [c.key for c in mapper.columns]
    assert "edited_text" in col_names, f"edited_text missing from Segment columns: {col_names}"


def test_segment_has_expansion_ratio_column() -> None:
    from sqlalchemy import inspect as sa_inspect

    from app.db.models import Segment

    mapper = sa_inspect(Segment)
    col_names = [c.key for c in mapper.columns]
    assert "expansion_ratio" in col_names, f"expansion_ratio missing from Segment columns: {col_names}"


def test_segment_flag_uses_native_enum_false() -> None:
    """Verify SegmentFlag enum columns have native_enum=False (SQLite compat)."""
    from app.db.models import SegmentFlag

    table = SegmentFlag.__table__
    for col in table.columns:
        if col.name in ("flag_type", "severity"):
            sa_type = col.type
            # SAEnum with native_enum=False stores as VARCHAR
            assert not getattr(sa_type, "native_enum", True), (
                f"Column '{col.name}' must use native_enum=False for SQLite compat"
            )


# ---------------------------------------------------------------------------
# SQLite round-trip tests (require db_session fixture from conftest.py)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_glossary_create_roundtrip(db_session) -> None:
    """Can insert and retrieve a Glossary row via SQLite."""
    from sqlalchemy import select

    from app.db.models import Glossary

    g = Glossary(name="Test Glossary", source_lang="en", target_lang="vi")
    db_session.add(g)
    await db_session.flush()

    result = await db_session.execute(select(Glossary).where(Glossary.id == g.id))
    fetched = result.scalar_one_or_none()
    assert fetched is not None
    assert fetched.name == "Test Glossary"
    assert fetched.source_lang == "en"
    assert fetched.target_lang == "vi"


@pytest.mark.asyncio
async def test_glossary_term_create_roundtrip(db_session) -> None:
    """Can insert GlossaryTerm linked to a Glossary."""
    from sqlalchemy import select

    from app.db.models import Glossary, GlossaryTerm

    g = Glossary(name="G2", source_lang="ja", target_lang="vi")
    db_session.add(g)
    await db_session.flush()

    term = GlossaryTerm(
        glossary_id=g.id,
        source_term="人工知能",
        target_term="Trí tuệ nhân tạo",
        notes="AI term",
    )
    db_session.add(term)
    await db_session.flush()

    result = await db_session.execute(
        select(GlossaryTerm).where(GlossaryTerm.glossary_id == g.id)
    )
    fetched = result.scalar_one_or_none()
    assert fetched is not None
    assert fetched.source_term == "人工知能"
    assert fetched.notes == "AI term"


@pytest.mark.asyncio
async def test_segment_flag_create_roundtrip(db_session) -> None:
    """Can insert SegmentFlag linked to a Segment (which requires a Job)."""
    import uuid

    from sqlalchemy import select

    from app.db.models import FlagSeverity, FlagType, Job, JobStatus, Segment, SegmentFlag

    job = Job(
        id=str(uuid.uuid4()),
        status=JobStatus.done,
        source_lang="en",
        target_lang="vi",
        input_format="docx",
        input_path="/tmp/test.docx",
        original_filename="test.docx",
    )
    db_session.add(job)
    await db_session.flush()

    seg_id = uuid.uuid4().hex[:16]
    seg = Segment(
        id=seg_id,
        seq_in_job=1,
        job_id=job.id,
        source_text="Hello world",
        structural_position="para:0",
    )
    db_session.add(seg)
    await db_session.flush()

    flag = SegmentFlag(
        segment_id=seg_id,
        segment_job_id=job.id,
        flag_type=FlagType.overflow,
        severity=FlagSeverity.warn,
        details={"ratio": 1.6, "threshold": 1.3},
    )
    db_session.add(flag)
    await db_session.flush()

    result = await db_session.execute(
        select(SegmentFlag).where(SegmentFlag.segment_id == seg_id)
    )
    fetched = result.scalar_one_or_none()
    assert fetched is not None
    assert fetched.flag_type == FlagType.overflow
    assert fetched.severity == FlagSeverity.warn
    assert fetched.details["ratio"] == 1.6


@pytest.mark.asyncio
async def test_segment_edited_text_and_expansion_ratio(db_session) -> None:
    """Segment.edited_text and expansion_ratio columns persist correctly."""
    import uuid

    from sqlalchemy import select

    from app.db.models import Job, JobStatus, Segment

    job = Job(
        id=str(uuid.uuid4()),
        status=JobStatus.done,
        source_lang="en",
        target_lang="vi",
        input_format="docx",
        input_path="/tmp/test2.docx",
        original_filename="test2.docx",
    )
    db_session.add(job)
    await db_session.flush()

    seg_id = uuid.uuid4().hex[:16]
    seg = Segment(
        id=seg_id,
        seq_in_job=1,
        job_id=job.id,
        source_text="Hello",
        translated_text="Xin chào",
        edited_text="Chào bạn",
        expansion_ratio=1.25,
        structural_position="para:0",
    )
    db_session.add(seg)
    await db_session.flush()

    result = await db_session.execute(select(Segment).where(Segment.id == seg_id))
    fetched = result.scalar_one_or_none()
    assert fetched is not None
    assert fetched.edited_text == "Chào bạn"
    assert fetched.expansion_ratio == pytest.approx(1.25)
