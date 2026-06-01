"""
Tests for POST /auth/register — TASK-3.4.

Covers:
- creates_active_non_admin: 201; User is_active=True, is_superuser=False; password hashed, not leaked
- duplicate_email_conflict: second registration with same email → 409; only one row in DB
- invalid_input_rejected: short password (<8) → 422; bad email format → 422
"""
from __future__ import annotations

import uuid
from typing import AsyncGenerator
from unittest.mock import AsyncMock, MagicMock

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

TEST_DB_URL = "sqlite+aiosqlite:///:memory:"


# ---------------------------------------------------------------------------
# Fixture: isolated app + SQLite DB + no real Redis/arq
# ---------------------------------------------------------------------------

@pytest_asyncio.fixture
async def register_app(tmp_path):
    """
    Yield (app, session_factory) with:
    - SQLite in-memory DB, all tables created
    - Dependency overrides for get_session, get_settings, get_arq_pool
    - app.state.redis / arq_pool / engine mocked so middleware + lifespan don't need real infra
    """
    from app.db.models import Base
    from app.db.session import get_session
    from app.api.deps import get_arq_pool, get_settings
    from app.main import app

    engine = create_async_engine(TEST_DB_URL, echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    session_factory = async_sessionmaker(engine, expire_on_commit=False)

    mock_arq = AsyncMock()
    mock_settings = MagicMock()
    mock_settings.database_url = MagicMock(get_secret_value=lambda: TEST_DB_URL)
    mock_settings.redis_url = "redis://localhost:6379/0"
    mock_settings.data_dir = str(tmp_path)
    mock_settings.license_signing_secret = MagicMock(
        get_secret_value=lambda: "test-license-signing-secret-placeholder"
    )
    # JWT fields needed by create_access_token / decode_access_token
    mock_settings.secret_key = MagicMock(
        get_secret_value=lambda: "test-secret-key-placeholder-for-unit-tests-only"
    )
    mock_settings.algorithm = "HS256"
    mock_settings.access_token_expire_minutes = 15
    mock_settings.refresh_token_expire_days = 30
    mock_settings.login_max_attempts = 5
    mock_settings.login_attempt_window_minutes = 10
    mock_settings.login_lockout_minutes = 15

    app.state.settings = mock_settings
    app.state.arq_pool = mock_arq
    app.state.redis = AsyncMock()
    app.state.engine = engine

    async def override_get_session() -> AsyncGenerator[AsyncSession, None]:
        async with session_factory() as session:
            yield session

    def override_get_arq_pool(request=None):
        return mock_arq

    def override_get_settings(request=None):
        return mock_settings

    app.dependency_overrides[get_session] = override_get_session
    app.dependency_overrides[get_arq_pool] = override_get_arq_pool
    app.dependency_overrides[get_settings] = override_get_settings

    yield app, session_factory

    app.dependency_overrides.clear()
    for attr in ("settings", "arq_pool", "redis", "engine"):
        try:
            delattr(app.state, attr)
        except AttributeError:
            pass
    await engine.dispose()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _unique_email() -> str:
    return f"test-{uuid.uuid4().hex[:8]}@example.com"


# ===========================================================================
# Test: creates_active_non_admin (3.4-a)
# ===========================================================================

@pytest.mark.asyncio
async def test_creates_active_non_admin(register_app):
    """
    POST /auth/register with valid payload:
    - returns 201
    - DB row has is_active=True, is_superuser=False
    - hashed_password != plaintext
    - verify_password(plaintext, hash) is True
    - response body does NOT contain password or hashed_password
    """
    from app.db.models import User
    from app.core.security import verify_password

    app, session_factory = register_app
    email = _unique_email()
    plaintext = "ValidPass1!"

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        r = await c.post(
            "/auth/register",
            json={"email": email, "password": plaintext, "full_name": "Test User"},
        )

    assert r.status_code == 201, r.text
    data = r.json()

    # Response fields check
    assert data["email"] == email.lower()
    assert data["is_active"] is True
    assert data["is_superuser"] is False
    assert "password" not in data
    assert "hashed_password" not in data

    # DB state check
    async with session_factory() as session:
        result = await session.execute(select(User).where(User.email == email.lower()))
        user = result.scalar_one_or_none()

    assert user is not None
    assert user.is_active is True
    assert user.is_superuser is False
    assert user.hashed_password != plaintext
    assert verify_password(plaintext, user.hashed_password) is True


# ===========================================================================
# Test: duplicate_email_conflict (3.4-b)
# ===========================================================================

@pytest.mark.asyncio
async def test_duplicate_email_conflict(register_app):
    """
    Registering the same email twice:
    - first POST → 201
    - second POST → 409 Conflict
    - exactly one User row with that email in the DB
    """
    from app.db.models import User

    app, session_factory = register_app
    email = _unique_email()
    body = {"email": email, "password": "ValidPass1!", "full_name": "Dup User"}

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        r1 = await c.post("/auth/register", json=body)
        assert r1.status_code == 201, r1.text

        r2 = await c.post("/auth/register", json=body)
        assert r2.status_code == 409, r2.text

    # Exactly one row in DB
    async with session_factory() as session:
        result = await session.execute(
            select(func.count()).select_from(User).where(User.email == email.lower())
        )
        count = result.scalar_one()

    assert count == 1, f"Expected 1 user row, found {count}"


# ===========================================================================
# Test: invalid_input_rejected (3.4-c)
# ===========================================================================

@pytest.mark.asyncio
async def test_invalid_input_rejected(register_app):
    """
    Validation failures return 422:
    - password shorter than 8 chars → 422
    - invalid email format → 422
    """
    app, _ = register_app

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        # Password too short (7 chars)
        r_short_pw = await c.post(
            "/auth/register",
            json={"email": _unique_email(), "password": "short12"},
        )
        assert r_short_pw.status_code == 422, r_short_pw.text

        # Invalid email
        r_bad_email = await c.post(
            "/auth/register",
            json={"email": "not-an-email", "password": "ValidPass1!"},
        )
        assert r_bad_email.status_code == 422, r_bad_email.text
