from __future__ import annotations

import os

# Set test-mode env vars BEFORE any app import triggers Settings() validation.
# Unit tests never hit real DashScope / real Postgres — values are placeholders.
os.environ.setdefault("DASHSCOPE_API_KEY", "sk-test-placeholder")
os.environ.setdefault("DATABASE_URL", "sqlite+aiosqlite:///:memory:")
os.environ.setdefault("REDIS_URL", "redis://localhost:6379/0")
os.environ.setdefault("DATA_DIR", "/tmp")

import numpy as np
import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from unittest.mock import AsyncMock, MagicMock

# ---------------------------------------------------------------------------
# In-memory SQLite for unit tests (no Postgres required)
# String(36) Job.id and String(16) Segment.id both work with SQLite — per W8/W12.
# ---------------------------------------------------------------------------
TEST_DB_URL = "sqlite+aiosqlite:///:memory:"


@pytest_asyncio.fixture(scope="session")
async def test_engine():
    """
    One SQLite in-memory engine per test session.
    Creates all tables from the ORM metadata on startup.
    """
    from app.db.models import Base

    engine = create_async_engine(TEST_DB_URL, echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    await engine.dispose()


@pytest_asyncio.fixture(scope="function")
async def db_session(test_engine):
    """
    AsyncSession per test, rolled back after each test.
    Per CLAUDE.md Python Testing: function-scoped for isolation.
    """
    session_factory = async_sessionmaker(test_engine, expire_on_commit=False)
    async with session_factory() as session:
        yield session
        await session.rollback()


# ---------------------------------------------------------------------------
# Mock Redis
# ---------------------------------------------------------------------------
@pytest.fixture
def mock_redis():
    """Mock Redis client for unit tests. Tracks publish calls."""
    redis = AsyncMock()
    redis.publish = AsyncMock(return_value=1)
    redis.ping = AsyncMock(return_value=True)
    redis.pubsub = MagicMock()
    return redis


# ---------------------------------------------------------------------------
# Mock AsyncOpenAI (for translate_batch unit tests)
# ---------------------------------------------------------------------------
@pytest.fixture
def mock_llm_client():
    """
    Mock AsyncOpenAI client with a configurable response.
    Default: returns 2 translated lines for 2 input segments.
    Override via: mock_llm_client.chat.completions.create.return_value = ...
    """
    client = AsyncMock()

    mock_response = MagicMock()
    mock_response.choices = [MagicMock()]
    mock_response.choices[0].message.content = "Hello world\nThis is a test"
    mock_response.usage = MagicMock(
        prompt_tokens=10, completion_tokens=12, total_tokens=22
    )
    client.chat.completions.create = AsyncMock(return_value=mock_response)
    return client


# ---------------------------------------------------------------------------
# arq ctx mock (combines all worker dependencies)
# ---------------------------------------------------------------------------
@pytest.fixture
def mock_arq_ctx(mock_redis, mock_llm_client, db_session):
    """
    Mock arq worker ctx dict with all keys the worker expects.
    session_factory returns the test db_session directly.
    """
    session_factory = MagicMock()
    session_factory.return_value.__aenter__ = AsyncMock(return_value=db_session)
    session_factory.return_value.__aexit__ = AsyncMock(return_value=False)

    return {
        "llm_client": mock_llm_client,
        "redis": mock_redis,
        "session_factory": session_factory,
    }


# ---------------------------------------------------------------------------
# Phase 2: Factory fixtures for Glossary, GlossaryTerm, SegmentFlag
# ---------------------------------------------------------------------------
# NOTE: These fixtures will only be usable after Plan 02 adds Glossary,
# GlossaryTerm, SegmentFlag to backend/src/app/db/models.py. The stub
# test files (created in Task 3 of this plan) will skip/xfail until then.
# ---------------------------------------------------------------------------

@pytest.fixture
def make_glossary(db_session):
    """Factory: create a Glossary row in the test DB.

    IMPORTANT: Uses commit() (not flush()) so rows are visible to the HTTP
    test client which runs in a separate session. flush() only makes rows
    visible within the same session; API-level tests need committed rows.
    """
    import uuid

    async def _make(
        name: str = "Test Glossary",
        source_lang: str = "vi",
        target_lang: str = "en",
    ):
        from app.db.models import Glossary
        g = Glossary(
            id=str(uuid.uuid4()),
            name=name,
            source_lang=source_lang,
            target_lang=target_lang,
        )
        db_session.add(g)
        await db_session.commit()
        await db_session.refresh(g)
        return g

    return _make


@pytest.fixture
def make_glossary_term(db_session):
    """Factory: create a GlossaryTerm row in the test DB.

    IMPORTANT: Uses commit() (not flush()) — same reason as make_glossary.
    API-level tests use a separate session and cannot see uncommitted rows.
    """
    import uuid

    async def _make(
        glossary_id: str,
        source_term: str = "AICore",
        target_term: str = "AICore",
        notes: str | None = None,
    ):
        from app.db.models import GlossaryTerm
        t = GlossaryTerm(
            id=str(uuid.uuid4()),
            glossary_id=glossary_id,
            source_term=source_term,
            target_term=target_term,
            notes=notes,
        )
        db_session.add(t)
        await db_session.commit()
        await db_session.refresh(t)
        return t

    return _make


@pytest.fixture
def make_segment_flag(db_session):
    """Factory: create a SegmentFlag row in the test DB."""
    import uuid

    async def _make(
        segment_id: str,
        segment_job_id: str,
        flag_type: str = "overflow",
        severity: str = "warn",
        details: dict | None = None,
    ):
        from app.db.models import SegmentFlag, FlagType, FlagSeverity
        f = SegmentFlag(
            id=str(uuid.uuid4()),
            segment_id=segment_id,
            segment_job_id=segment_job_id,
            flag_type=FlagType(flag_type),
            severity=FlagSeverity(severity),
            details=details or {},
        )
        db_session.add(f)
        await db_session.flush()
        return f

    return _make


# ---------------------------------------------------------------------------
# Phase 4: PaddleOCR mock fixtures (D-04-28)
# ---------------------------------------------------------------------------

def _make_bbox(x0: int, y0: int, x1: int, y1: int) -> np.ndarray:
    """Create a PaddleOCR block_bbox polygon array (4,2) from an axis-aligned rect."""
    return np.array([[x0, y0], [x1, y0], [x1, y1], [x0, y1]], dtype=np.int16)


@pytest.fixture
def mock_ppstructurev3():
    """Canned PP-StructureV3 output for unit tests (D-04-28). No real PaddleOCR needed.

    Returns a mock pipeline whose .predict() returns one result with two text blocks:
    - block 0: paragraph_title "Tiêu đề đoạn văn" (confidence ~0.89)
    - block 1: text "Nội dung đoạn văn về dịch thuật AI." (confidence ~0.89)
    Page-mean confidence = mean([0.92, 0.85, 0.91]) ≈ 0.893 → above 0.7 threshold.
    """
    mock_res = MagicMock()
    mock_res.json = {
        "layout_parsing_result": {
            "parsing_res_list": [
                {
                    "block_bbox": _make_bbox(10, 10, 200, 40),
                    "block_label": "paragraph_title",
                    "block_content": "Tiêu đề đoạn văn",
                    "block_id": 0,
                    "block_order": 0,
                },
                {
                    "block_bbox": _make_bbox(10, 50, 400, 150),
                    "block_label": "text",
                    "block_content": "Nội dung đoạn văn về dịch thuật AI.",
                    "block_id": 1,
                    "block_order": 1,
                },
            ]
        },
        "overall_ocr_res": {"rec_scores": [0.92, 0.85, 0.91]},
    }
    mock_pipeline = MagicMock()
    mock_pipeline.predict.return_value = [mock_res]
    return mock_pipeline


@pytest.fixture
def low_confidence_mock_ppstructurev3():
    """PP-StructureV3 output with low confidence (mean < 0.7) for OCR-02 tests.

    Page-mean confidence = mean([0.45, 0.38, 0.52]) ≈ 0.45 → below 0.7 threshold.
    Triggers needs_review banner (D-04-02).
    """
    mock_res = MagicMock()
    mock_res.json = {
        "layout_parsing_result": {
            "parsing_res_list": [
                {
                    "block_bbox": _make_bbox(10, 10, 200, 40),
                    "block_label": "text",
                    "block_content": "Blurry scanned text",
                    "block_id": 0,
                    "block_order": 0,
                },
            ]
        },
        "overall_ocr_res": {"rec_scores": [0.45, 0.38, 0.52]},  # mean ≈ 0.45 < 0.7
    }
    mock_pipeline = MagicMock()
    mock_pipeline.predict.return_value = [mock_res]
    return mock_pipeline
