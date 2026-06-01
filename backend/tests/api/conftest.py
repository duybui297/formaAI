"""
Shared fixtures for tests/api/.

app_and_tmp: provides (FastAPI app, arq mock) with SQLite in-memory DB,
temp data_dir, and dependency overrides for get_session/get_arq_pool/get_settings,
and get_current_active_user (superuser, so entitlement enforcement is bypassed).
Used by test_upload.py and test_upload_error_ux.py.
"""
from __future__ import annotations

import uuid
from unittest.mock import AsyncMock, MagicMock

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

TEST_DB_URL = "sqlite+aiosqlite:///:memory:"


def _make_superuser() -> "User":  # noqa: F821
    """Create an in-memory superuser for dependency override (no DB row needed)."""
    from app.db.models import User
    return User(
        id=str(uuid.uuid4()),
        email="superuser@test.com",
        hashed_password="x",
        is_active=True,
        is_superuser=True,
    )


@pytest_asyncio.fixture
async def app_and_tmp(tmp_path):
    """
    Yield a (app, arq_mock) tuple with:
    - SQLite in-memory DB, tables created
    - tmp_path used as data_dir
    - arq_pool mocked (enqueue_job is an AsyncMock)
    - get_current_active_user overridden with a superuser so entitlement
      checks are bypassed (TASK-3.7: superuser → ENTERPRISE, always allowed)

    Uses dependency_overrides for get_session, get_arq_pool, get_settings,
    and get_current_active_user so the app runs without real Redis/DB/arq/JWT.
    """
    from app.db.models import Base
    from app.db.session import get_session
    from app.api.deps import get_arq_pool, get_current_active_user, get_settings
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
        ocr_text_density_threshold=0.05,
    )

    app.state.settings = mock_settings
    app.state.arq_pool = mock_arq
    app.state.redis = AsyncMock()
    app.state.engine = engine

    superuser = _make_superuser()

    async def override_get_session():
        async with session_factory() as session:
            yield session

    def override_get_arq_pool(request=None):
        return mock_arq

    def override_get_settings(request=None):
        return mock_settings

    def override_get_current_active_user():
        return superuser

    app.dependency_overrides[get_session] = override_get_session
    app.dependency_overrides[get_arq_pool] = override_get_arq_pool
    app.dependency_overrides[get_settings] = override_get_settings
    app.dependency_overrides[get_current_active_user] = override_get_current_active_user

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
