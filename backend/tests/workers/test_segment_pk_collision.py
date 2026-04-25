"""Tests for compound PK (job_id, id) on segments + run_index/run_group_size fields.

Gap-closure 02-10:
- Test 1: same content hash can be inserted under two different job_ids (no PK collision)
- Test 2: run_index and run_group_size round-trip correctly through the ORM
- Test 3: accessing .run_index on a loaded ORM Segment does not raise AttributeError
"""
from __future__ import annotations

import pytest
import pytest_asyncio
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.db.models import Base, Job, JobStatus, Segment
from app.pipeline.segment import make_segment_id

DATABASE_URL = "sqlite+aiosqlite:///:memory:"


@pytest_asyncio.fixture(scope="module")
async def engine():
    e = create_async_engine(DATABASE_URL, echo=False)
    async with e.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield e
    await e.dispose()


@pytest_asyncio.fixture
async def session(engine):
    factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with factory() as s:
        yield s


async def test_same_content_two_jobs_no_pk_collision(session: AsyncSession) -> None:
    """Compound PK allows same segment id in different jobs — no IntegrityError."""
    job1 = Job(
        id="job-pk-01",
        status=JobStatus.done,
        source_lang="en",
        target_lang="vi",
        input_format="docx",
        input_path="/tmp/a.docx",
        original_filename="a.docx",
    )
    job2 = Job(
        id="job-pk-02",
        status=JobStatus.done,
        source_lang="en",
        target_lang="vi",
        input_format="docx",
        input_path="/tmp/b.docx",
        original_filename="b.docx",
    )
    session.add_all([job1, job2])
    await session.flush()

    seg_id = make_segment_id("Hello world", "para.0")
    seg1 = Segment(
        id=seg_id,
        job_id="job-pk-01",
        seq_in_job=0,
        source_text="Hello world",
        structural_position="para.0",
        run_index=None,
        run_group_size=1,
    )
    seg2 = Segment(
        id=seg_id,
        job_id="job-pk-02",
        seq_in_job=0,
        source_text="Hello world",
        structural_position="para.0",
        run_index=None,
        run_group_size=1,
    )
    session.add_all([seg1, seg2])
    await session.commit()  # must NOT raise IntegrityError

    result = await session.execute(select(Segment).where(Segment.id == seg_id))
    rows = result.scalars().all()
    assert len(rows) == 2, f"Expected 2 rows (one per job), got {len(rows)}"


async def test_segment_orm_has_run_fields(session: AsyncSession) -> None:
    """ORM Segment stores and retrieves run_index and run_group_size correctly."""
    job = Job(
        id="job-run-01",
        status=JobStatus.done,
        source_lang="en",
        target_lang="vi",
        input_format="docx",
        input_path="/tmp/r.docx",
        original_filename="r.docx",
    )
    session.add(job)
    await session.flush()

    seg_id = make_segment_id("Run field test", "para.1")
    seg = Segment(
        id=seg_id,
        job_id="job-run-01",
        seq_in_job=0,
        source_text="Run field test",
        structural_position="para.1",
        run_index=2,
        run_group_size=3,
    )
    session.add(seg)
    await session.commit()

    result = await session.execute(
        select(Segment).where(Segment.id == seg_id, Segment.job_id == "job-run-01")
    )
    loaded = result.scalar_one()
    assert loaded.run_index == 2
    assert loaded.run_group_size == 3


async def test_orm_segment_run_index_no_attribute_error(session: AsyncSession) -> None:
    """Accessing .run_index on a loaded ORM Segment does not raise AttributeError.

    This was the root cause of the export failure in UAT Test 4: the reassembler
    accessed seg.run_index but the column did not exist on the ORM model.
    """
    job = Job(
        id="job-attr-01",
        status=JobStatus.done,
        source_lang="en",
        target_lang="vi",
        input_format="docx",
        input_path="/tmp/x.docx",
        original_filename="x.docx",
    )
    session.add(job)
    await session.flush()

    seg_id = make_segment_id("Attribute error test", "para.2")
    seg = Segment(
        id=seg_id,
        job_id="job-attr-01",
        seq_in_job=0,
        source_text="Attribute error test",
        structural_position="para.2",
        run_index=None,
        run_group_size=1,
    )
    session.add(seg)
    await session.commit()

    result = await session.execute(
        select(Segment).where(Segment.id == seg_id, Segment.job_id == "job-attr-01")
    )
    loaded = result.scalar_one()
    # These must not raise AttributeError (was the root cause of export failure)
    _ = loaded.run_index       # None is valid for paragraph-level segments
    _ = loaded.run_group_size  # 1 is the default
    assert True  # reaching here means no AttributeError raised
