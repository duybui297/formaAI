"""
Tests for glossary_service.run_post_check.

GLOS-04: per-batch post-translation check
LAYOUT-01: overflow detection via expansion_ratio
D-02-07: terms shorter than 2 chars skipped in glossary violation check
"""
from __future__ import annotations

import uuid

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.db.models import Base, FlagSeverity, FlagType, Job, JobStatus, Segment, SegmentFlag

TEST_DB_URL = "sqlite+aiosqlite:///:memory:"


@pytest_asyncio.fixture(scope="module")
async def engine():
    e = create_async_engine(TEST_DB_URL, echo=False)
    async with e.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield e
    await e.dispose()


@pytest_asyncio.fixture
async def session(engine):
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as sess:
        yield sess
        await sess.rollback()


async def _make_job(session) -> Job:
    job = Job(
        id=str(uuid.uuid4()),
        status=JobStatus.done,
        source_lang="en",
        target_lang="vi",
        input_format="docx",
        input_path="/tmp/source.docx",
        original_filename="test.docx",
    )
    session.add(job)
    await session.commit()
    await session.refresh(job)
    return job


async def _make_segment(session, job_id: str, seq: int, source_text: str) -> Segment:
    seg_id = (job_id.replace("-", "")[:12] + f"{seq:04d}")[:16]
    seg = Segment(
        id=seg_id,
        seq_in_job=seq,
        job_id=job_id,
        source_text=source_text,
        translated_text=None,
        structural_position=f"para.{seq}",
    )
    session.add(seg)
    await session.commit()
    return seg


# ---------------------------------------------------------------------------
# Expansion ratio + overflow flag
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_run_post_check_stores_expansion_ratio(session):
    """run_post_check stores expansion_ratio on each segment."""
    from app.services.glossary_service import run_post_check
    from sqlalchemy import select

    job = await _make_job(session)
    seg = await _make_segment(session, job.id, 1, "Hello")

    translated_map = {seg.id: "Xin chào"}

    await run_post_check(
        session=session,
        batch_segs=[seg],
        translated_map=translated_map,
        glossary=None,
        source_lang="en",
        target_lang="vi",
        expansion_thresholds={"en->vi": 1.3},
    )

    result = await session.execute(select(Segment).where(Segment.id == seg.id))
    updated_seg = result.scalar_one()
    assert updated_seg.expansion_ratio is not None
    # "Xin chào" (8 chars) / "Hello" (5 chars) = 1.6
    assert abs(updated_seg.expansion_ratio - 8 / 5) < 0.01


@pytest.mark.asyncio
async def test_run_post_check_writes_overflow_flag_when_ratio_exceeds_threshold(session):
    """run_post_check writes overflow flag when expansion_ratio > threshold."""
    from app.services.glossary_service import run_post_check
    from sqlalchemy import select

    job = await _make_job(session)
    seg = await _make_segment(session, job.id, 2, "Hi")

    # source=2 chars, translated=10 chars → ratio=5.0, threshold=1.3 → overflow
    translated_map = {seg.id: "Xin chào bạn"}

    await run_post_check(
        session=session,
        batch_segs=[seg],
        translated_map=translated_map,
        glossary=None,
        source_lang="en",
        target_lang="vi",
        expansion_thresholds={"en->vi": 1.3},
    )

    result = await session.execute(
        select(SegmentFlag).where(
            SegmentFlag.segment_id == seg.id,
            SegmentFlag.flag_type == FlagType.overflow,
        )
    )
    flags = result.scalars().all()
    assert len(flags) >= 1
    assert flags[0].severity == FlagSeverity.warn


@pytest.mark.asyncio
async def test_run_post_check_no_overflow_flag_when_ratio_within_threshold(session):
    """run_post_check does NOT write overflow flag when ratio is within threshold."""
    from app.services.glossary_service import run_post_check
    from sqlalchemy import select

    job = await _make_job(session)
    seg = await _make_segment(session, job.id, 3, "Hello world from me")

    # source=19 chars, translated=20 chars → ratio~1.05, threshold=1.3 → no overflow
    translated_map = {seg.id: "Xin chào thế giới từ"}

    await run_post_check(
        session=session,
        batch_segs=[seg],
        translated_map=translated_map,
        glossary=None,
        source_lang="en",
        target_lang="vi",
        expansion_thresholds={"en->vi": 1.3},
    )

    result = await session.execute(
        select(SegmentFlag).where(
            SegmentFlag.segment_id == seg.id,
            SegmentFlag.flag_type == FlagType.overflow,
        )
    )
    flags = result.scalars().all()
    assert len(flags) == 0


# ---------------------------------------------------------------------------
# Glossary violation check (D-02-07: skip terms < 2 chars)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_run_post_check_writes_glossary_violation_flag(session):
    """run_post_check writes glossary_violation when term missing from translation."""
    from app.services.glossary_service import run_post_check
    from sqlalchemy import select

    job = await _make_job(session)
    seg = await _make_segment(session, job.id, 4, "The API call failed")

    # "API" appears in source but NOT in translation — should be flagged
    translated_map = {seg.id: "Cuộc gọi thất bại"}

    await run_post_check(
        session=session,
        batch_segs=[seg],
        translated_map=translated_map,
        glossary={"API": "API"},
        source_lang="en",
        target_lang="vi",
        expansion_thresholds={},
    )

    result = await session.execute(
        select(SegmentFlag).where(
            SegmentFlag.segment_id == seg.id,
            SegmentFlag.flag_type == FlagType.glossary_violation,
        )
    )
    flags = result.scalars().all()
    assert len(flags) >= 1
    assert "API" in flags[0].details["violated_terms"]


@pytest.mark.asyncio
async def test_run_post_check_skips_short_terms_per_d02_07(session):
    """D-02-07: terms shorter than 2 chars are skipped in glossary violation check."""
    from app.services.glossary_service import run_post_check
    from sqlalchemy import select

    job = await _make_job(session)
    seg = await _make_segment(session, job.id, 5, "I went to the store")

    # "I" is 1 char — must be skipped per D-02-07
    translated_map = {seg.id: "Tôi đến cửa hàng"}

    await run_post_check(
        session=session,
        batch_segs=[seg],
        translated_map=translated_map,
        glossary={"I": "Tôi"},  # 1-char term — should be SKIPPED
        source_lang="en",
        target_lang="vi",
        expansion_thresholds={},
    )

    result = await session.execute(
        select(SegmentFlag).where(
            SegmentFlag.segment_id == seg.id,
            SegmentFlag.flag_type == FlagType.glossary_violation,
        )
    )
    flags = result.scalars().all()
    # No flag — short term was skipped
    assert len(flags) == 0


@pytest.mark.asyncio
async def test_run_post_check_no_violation_when_term_present(session):
    """No glossary_violation flag when target term appears in translation."""
    from app.services.glossary_service import run_post_check
    from sqlalchemy import select

    job = await _make_job(session)
    seg = await _make_segment(session, job.id, 6, "Use the REST API here")

    # "API" appears in source AND in translation — no violation
    translated_map = {seg.id: "Sử dụng REST API ở đây"}

    await run_post_check(
        session=session,
        batch_segs=[seg],
        translated_map=translated_map,
        glossary={"API": "API"},
        source_lang="en",
        target_lang="vi",
        expansion_thresholds={},
    )

    result = await session.execute(
        select(SegmentFlag).where(
            SegmentFlag.segment_id == seg.id,
            SegmentFlag.flag_type == FlagType.glossary_violation,
        )
    )
    flags = result.scalars().all()
    assert len(flags) == 0


# ---------------------------------------------------------------------------
# LLM refusal detection
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_run_post_check_writes_llm_refusal_flag(session):
    """run_post_check writes llm_refusal flag when translation contains refusal text."""
    from app.services.glossary_service import run_post_check
    from sqlalchemy import select

    job = await _make_job(session)
    seg = await _make_segment(session, job.id, 7, "Sensitive content here")

    translated_map = {seg.id: "I cannot translate this content"}

    await run_post_check(
        session=session,
        batch_segs=[seg],
        translated_map=translated_map,
        glossary=None,
        source_lang="en",
        target_lang="vi",
        expansion_thresholds={},
    )

    result = await session.execute(
        select(SegmentFlag).where(
            SegmentFlag.segment_id == seg.id,
            SegmentFlag.flag_type == FlagType.llm_refusal,
        )
    )
    flags = result.scalars().all()
    assert len(flags) >= 1
    assert flags[0].severity == FlagSeverity.block
