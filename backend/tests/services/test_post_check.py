"""Post-translation check tests — GLOS-04, LAYOUT-01.

Stubs: will pass after Plan 03 implements run_post_check in glossary_service.py.
Note: run_post_check is in glossary_service.py (not translate_worker.py).

IMPORTANT: test_expansion_ratio_overflow_flag uses a real Segment DB row (not just
FakeSeg) so that run_post_check can write expansion_ratio back to the DB and the
test can assert the SegmentFlag was persisted via a DB query.
"""
from __future__ import annotations

import pytest


@pytest.mark.asyncio
@pytest.mark.xfail(reason="Requires Plan 03 run_post_check implementation", strict=False)
async def test_glossary_violation_flag_written(db_session, make_glossary, make_glossary_term):
    """run_post_check writes glossary_violation flag when term absent from output — GLOS-04."""
    from app.services.glossary_service import run_post_check
    from app.db.models import SegmentFlag, FlagType
    from sqlalchemy import select

    g = await make_glossary()
    await make_glossary_term(g.id, source_term="AICore", target_term="AICore")
    glossary = {"AICore": "AICore"}

    class FakeSeg:
        id = "seg001"
        source_text = "xin ch\xe0o từ AICore"

    translated_map = {"seg001": "hello from SomeOtherCompany"}
    await run_post_check(
        session=db_session,
        batch_segs=[FakeSeg()],
        translated_map=translated_map,
        glossary=glossary,
        source_lang="vi",
        target_lang="en",
        expansion_thresholds={"vi->en": 0.9},
    )
    result = await db_session.execute(
        select(SegmentFlag).where(SegmentFlag.segment_id == "seg001")
    )
    flags = result.scalars().all()
    assert any(f.flag_type == FlagType.glossary_violation for f in flags)


@pytest.mark.asyncio
@pytest.mark.xfail(reason="Requires Plan 03 run_post_check implementation", strict=False)
async def test_short_term_skipped(db_session):
    """run_post_check skips terms shorter than 2 chars — D-02-07."""
    from app.services.glossary_service import run_post_check
    from app.db.models import SegmentFlag
    from sqlalchemy import select

    class FakeSeg:
        id = "seg002"
        source_text = "A single letter"

    glossary = {"A": "B"}  # Both less than 2 chars — must be skipped
    translated_map = {"seg002": "No B in output"}
    await run_post_check(
        session=db_session,
        batch_segs=[FakeSeg()],
        translated_map=translated_map,
        glossary=glossary,
        source_lang="en",
        target_lang="vi",
        expansion_thresholds={},
    )
    result = await db_session.execute(
        select(SegmentFlag).where(SegmentFlag.segment_id == "seg002")
    )
    flags = result.scalars().all()
    assert len(flags) == 0


@pytest.mark.asyncio
@pytest.mark.xfail(reason="Requires Plan 03 run_post_check implementation", strict=False)
async def test_expansion_ratio_overflow_flag(db_session):
    """run_post_check emits overflow flag when ratio exceeds threshold — LAYOUT-01.

    Uses a real Segment DB row (not just FakeSeg) so that:
    - run_post_check can write expansion_ratio via UPDATE Segment WHERE id = seg.id
    - The SegmentFlag INSERT has a valid FK to segments.id (no FK violation)
    - We can assert the flag was persisted via a real DB query
    """
    import uuid
    from app.db.models import Segment, SegmentFlag, FlagType
    from app.services.glossary_service import run_post_check
    from sqlalchemy import select

    # Insert a real Segment row — run_post_check writes expansion_ratio back to it
    seg_id = str(uuid.uuid4())
    seg = Segment(
        id=seg_id,
        job_id="fake-job-id",  # FK not enforced in SQLite test DB
        seq_in_job=0,
        source_text="ab",  # 2 chars
        translated_text="abcdefghij",  # 10 chars → ratio=5.0 > threshold 1.3
    )
    db_session.add(seg)
    await db_session.flush()

    translated_map = {seg_id: "abcdefghij"}
    await run_post_check(
        session=db_session,
        batch_segs=[seg],
        translated_map=translated_map,
        glossary=None,
        source_lang="en",
        target_lang="vi",
        expansion_thresholds={"en->vi": 1.3},
    )
    result = await db_session.execute(
        select(SegmentFlag).where(SegmentFlag.segment_id == seg_id)
    )
    flags = result.scalars().all()
    assert any(f.flag_type == FlagType.overflow for f in flags)


@pytest.mark.asyncio
@pytest.mark.xfail(reason="Requires Plan 03 run_post_check implementation", strict=False)
async def test_placeholder_mismatch_flag_written(db_session):
    """run_post_check writes placeholder_mismatch flag when token missing from output — WARNING 2 fix."""
    from app.services.glossary_service import run_post_check
    from app.db.models import SegmentFlag, FlagType
    from sqlalchemy import select

    class FakeSeg:
        id = "seg004"
        source_text = "Visit ⟦T1⟧ for details"  # T1 placeholder from Phase 1 CORE-05

    translated_map = {"seg004": "Truy cập để biết chi tiết"}  # ⟦T1⟧ missing
    await run_post_check(
        session=db_session,
        batch_segs=[FakeSeg()],
        translated_map=translated_map,
        glossary=None,
        source_lang="en",
        target_lang="vi",
        expansion_thresholds={},
    )
    result = await db_session.execute(
        select(SegmentFlag).where(SegmentFlag.segment_id == "seg004")
    )
    flags = result.scalars().all()
    assert any(f.flag_type == FlagType.placeholder_mismatch for f in flags)


@pytest.mark.asyncio
@pytest.mark.xfail(reason="Requires Plan 03 run_post_check implementation", strict=False)
async def test_llm_refusal_flag_written(db_session):
    """run_post_check writes llm_refusal flag when output identical to source — heuristic: len > 8 AND identical.

    The heuristic requires len(source_stripped) > 8 to avoid false positives on short
    acronyms (e.g. 'AI' → 'AI' is correct, not a refusal). 'Hello world' is 11 chars
    and passes unchanged, so the flag should fire.
    """
    from app.services.glossary_service import run_post_check
    from app.db.models import SegmentFlag, FlagType
    from sqlalchemy import select

    class FakeSeg:
        id = "seg005"
        source_text = "Hello world"  # 11 chars > 8 threshold

    # LLM returned the source unchanged (refusal heuristic: len > 8 AND identical)
    translated_map = {"seg005": "Hello world"}
    await run_post_check(
        session=db_session,
        batch_segs=[FakeSeg()],
        translated_map=translated_map,
        glossary=None,
        source_lang="en",
        target_lang="vi",
        expansion_thresholds={},
    )
    result = await db_session.execute(
        select(SegmentFlag).where(SegmentFlag.segment_id == "seg005")
    )
    flags = result.scalars().all()
    assert any(f.flag_type == FlagType.llm_refusal for f in flags)
