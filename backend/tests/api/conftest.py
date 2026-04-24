"""
Shared fixtures for tests/api/.

app_and_tmp: provides (FastAPI app, arq mock) with SQLite in-memory DB,
temp data_dir, and dependency overrides for get_session/get_arq_pool/get_settings.
Used by test_upload.py and test_upload_error_ux.py.
"""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

TEST_DB_URL = "sqlite+aiosqlite:///:memory:"


@pytest_asyncio.fixture
async def app_and_tmp(tmp_path):
    """
    Yield a (app, arq_mock) tuple with:
    - SQLite in-memory DB, tables created
    - tmp_path used as data_dir
    - arq_pool mocked (enqueue_job is an AsyncMock)

    Uses dependency_overrides for get_session, get_arq_pool, and get_settings
    so the app runs without real Redis/DB/arq.
    """
    from app.db.models import Base
    from app.db.session import get_session
    from app.api.dependencies import get_arq_pool, get_settings
    from app.main import app

    engine = create_async_engine(TEST_DB_URL, echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    session_factory = async_sessionmaker(engine, expire_on_commit=False)

    mock_arq = AsyncMock()
    mock_arq.enqueue_job = AsyncMock(return_value=MagicMock())

    mock_settings = MagicMock(
        database_url=MagicMock(get_secret_value=lambda: TEST_DB_URL),
        redis_url="redis://localhost:6379/0",
        data_dir=str(tmp_path),
    )

    app.state.settings = mock_settings
    app.state.arq_pool = mock_arq
    app.state.redis = AsyncMock()
    app.state.engine = engine

    async def override_get_session():
        async with session_factory() as session:
            yield session

    def override_get_arq_pool(request=None):
        return mock_arq

    def override_get_settings(request=None):
        return mock_settings

    app.dependency_overrides[get_session] = override_get_session
    app.dependency_overrides[get_arq_pool] = override_get_arq_pool
    app.dependency_overrides[get_settings] = override_get_settings

    yield app, mock_arq

    app.dependency_overrides.clear()
    try:
        del app.state.settings
        del app.state.arq_pool
        del app.state.redis
        del app.state.engine
    except AttributeError:
        pass

    await engine.dispose()
