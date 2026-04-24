from __future__ import annotations

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
