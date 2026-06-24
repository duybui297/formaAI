"""
Tests for POST /api/v1/auth/signup — US-1.1.

Covers:
- creates_active_non_admin: 201; User is_active=True, is_superuser=False; password hashed, not leaked;
  default Free License (TRIAL) created in the same transaction
- duplicate_email_conflict: second registration with same email → 409; only one row in DB;
  message contains "Sign in?"
- invalid_input_rejected: short password (<8) → 422; bad email format → 422;
  weak password (no uppercase / no digit) → 422
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

class _FakePipeline:
    """Async pipeline mock that emulates Redis pipeline with incr+expire."""

    def __init__(self) -> None:
        self._ops: list = []

    def incr(self, key: str):
        self._ops.append(("incr", key))
        return self

    def expire(self, key: str, ttl: int):
        self._ops.append(("expire", key, ttl))
        return self

    async def execute(self) -> list:
        results: list = []
        for op in self._ops:
            if op[0] == "incr":
                self._counts[op[1]] = self._counts.get(op[1], 0) + 1
                results.append(self._counts[op[1]])
            else:
                results.append(True)
        self._ops.clear()
        return results


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

    # Redis mock with a shared counter dict and a fake pipeline
    counts: dict[str, int] = {}

    def make_pipeline():
        pipe = _FakePipeline()
        pipe._counts = counts
        return pipe

    mock_redis = AsyncMock()
    mock_redis.pipeline = MagicMock(side_effect=make_pipeline)
    mock_redis.get = AsyncMock(side_effect=lambda k: counts.get(k))
    mock_redis.setex = AsyncMock()
    mock_redis.delete = AsyncMock()
    mock_redis.aclose = AsyncMock()

    mock_settings = MagicMock()
    mock_settings.database_url = MagicMock(get_secret_value=lambda: TEST_DB_URL)
    mock_settings.redis_url = "redis://localhost:6379/0"
    mock_settings.data_dir = str(tmp_path)
    mock_settings.license_signing_secret = MagicMock(
        get_secret_value=lambda: "test-license-signing-secret-placeholder"
    )
    mock_settings.secret_key = MagicMock(
        get_secret_value=lambda: "test-secret-key-placeholder-for-unit-tests-only"
    )
    mock_settings.algorithm = "HS256"
    mock_settings.access_token_expire_minutes = 15
    mock_settings.refresh_token_expire_days = 30
    mock_settings.login_max_attempts = 5
    mock_settings.login_attempt_window_minutes = 10
    mock_settings.login_lockout_minutes = 15
    mock_settings.password_reset_token_expire_minutes = 60
    # US-1.1 fields
    mock_settings.email_verification_token_expire_minutes = 1440
    mock_settings.signup_rate_limit_per_minute = 5
    mock_settings.app_url = "http://localhost:8080"

    app.state.settings = mock_settings
    app.state.arq_pool = mock_arq
    app.state.redis = mock_redis
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
# Test: creates_active_non_admin — extended for US-1.1
# ===========================================================================

@pytest.mark.asyncio
async def test_creates_active_non_admin(register_app):
    """
    POST /api/v1/auth/signup with valid payload:
    - returns 201
    - DB row has is_active=True, is_superuser=False, email_verified=False
    - hashed_password != plaintext
    - verify_password(plaintext, hash) is True
    - response body does NOT contain password or hashed_password
    - default Free License (TRIAL) is created in the same transaction
    """
    from app.db.models import User, License
    from app.core.security import verify_password

    app, session_factory = register_app
    email = _unique_email()
    plaintext = "ValidPass1!"

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        r = await c.post(
            "/api/v1/auth/signup",
            json={"email": email, "password": plaintext, "full_name": "Test User"},
        )

    assert r.status_code == 201, r.text
    data = r.json()

    assert data["email"] == email.lower()
    assert data["is_active"] is True
    assert data["is_superuser"] is False
    assert "password" not in data
    assert "hashed_password" not in data
    assert "message" in data

    async with session_factory() as session:
        result = await session.execute(select(User).where(User.email == email.lower()))
        user = result.scalar_one_or_none()

    assert user is not None
    assert user.is_active is True
    assert user.is_superuser is False
    assert user.email_verified is False
    assert user.hashed_password != plaintext
    assert verify_password(plaintext, user.hashed_password) is True

    # US-1.1: default Free license row in the same tx
    async with session_factory() as session:
        result = await session.execute(select(License).where(License.customer_id == user.id))
        lic = result.scalar_one_or_none()
    assert lic is not None, "Default Free license should be created at signup"
    assert lic.tier.value == "TRIAL"
    assert lic.status.value == "ACTIVE"
    assert lic.expired_at is not None


# ===========================================================================
# Test: duplicate_email_conflict — extended for US-1.1 message
# ===========================================================================

@pytest.mark.asyncio
async def test_duplicate_email_conflict(register_app):
    """
    Registering the same email twice:
    - first POST → 201
    - second POST → 409 Conflict
    - exactly one User row with that email in the DB
    - US-1.1 message contains "Sign in?"
    """
    from app.db.models import User

    app, session_factory = register_app
    email = _unique_email()
    body = {"email": email, "password": "ValidPass1!", "full_name": "Dup User"}

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        r1 = await c.post("/api/v1/auth/signup", json=body)
        assert r1.status_code == 201, r1.text

        r2 = await c.post("/api/v1/auth/signup", json=body)
        assert r2.status_code == 409, r2.text
        assert "Sign in?" in r2.json()["detail"]

    async with session_factory() as session:
        result = await session.execute(
            select(func.count()).select_from(User).where(User.email == email.lower())
        )
        count = result.scalar_one()

    assert count == 1, f"Expected 1 user row, found {count}"


# ===========================================================================
# Test: invalid_input_rejected — extended for US-1.1 password rules
# ===========================================================================

@pytest.mark.asyncio
async def test_invalid_input_rejected(register_app):
    """
    Validation failures return 422:
    - password shorter than 8 chars → 422
    - invalid email format → 422
    - weak password (no uppercase) → 422
    - weak password (no digit) → 422
    """
    app, _ = register_app

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        r_short_pw = await c.post(
            "/api/v1/auth/signup",
            json={"email": _unique_email(), "password": "short12"},
        )
        assert r_short_pw.status_code == 422, r_short_pw.text

        r_bad_email = await c.post(
            "/api/v1/auth/signup",
            json={"email": "not-an-email", "password": "ValidPass1!"},
        )
        assert r_bad_email.status_code == 422, r_bad_email.text

        r_no_upper = await c.post(
            "/api/v1/auth/signup",
            json={"email": _unique_email(), "password": "weakpass1"},
        )
        assert r_no_upper.status_code == 422, r_no_upper.text

        r_no_digit = await c.post(
            "/api/v1/auth/signup",
            json={"email": _unique_email(), "password": "WeakPassword"},
        )
        assert r_no_digit.status_code == 422, r_no_digit.text


# ===========================================================================
# US-1.1: rate-limit 5/min/IP
# ===========================================================================

@pytest.mark.asyncio
async def test_signup_rate_limit(register_app):
    """The 6th signup attempt from the same IP within 60s returns 429.

    Each request must use a different email (otherwise 409 would mask the 429).
    """
    from app.main import app

    app, _ = register_app

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        for i in range(5):
            body = {
                "email": _unique_email(),
                "password": "ValidPass1!",
                "full_name": f"Rate Test {i}",
            }
            r = await c.post("/api/v1/auth/signup", json=body)
            assert r.status_code == 201, f"Attempt {i + 1}: {r.text}"
        # 6th attempt should be rate-limited — use a fresh email
        r6 = await c.post(
            "/api/v1/auth/signup",
            json={
                "email": _unique_email(),
                "password": "ValidPass1!",
                "full_name": "Rate Test 6",
            },
        )
        assert r6.status_code == 429, r6.text
        assert "Too many signup attempts" in r6.json()["detail"]


# ===========================================================================
# US-1.1: login is blocked when email_verified=False
# ===========================================================================

@pytest.mark.asyncio
async def test_login_blocked_when_unverified(register_app):
    """After signup, login must return 403 until email is verified."""
    from app.db.models import User
    from app.main import app

    app, session_factory = register_app
    email = _unique_email()
    password = "ValidPass1!"

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        r = await c.post(
            "/api/v1/auth/signup",
            json={"email": email, "password": password, "full_name": "Unverified User"},
        )
        assert r.status_code == 201

        r_login = await c.post(
            "/api/v1/auth/login",
            json={"email": email, "password": password},
        )
        assert r_login.status_code == 403, r_login.text
        assert "verify your email" in r_login.json()["detail"].lower()


# ===========================================================================
# US-1.1: verify-email endpoint
# ===========================================================================

@pytest.mark.asyncio
async def test_verify_email_success(register_app):
    """POST /api/v1/auth/verify-email with a valid token marks user.email_verified=True
    AND then login succeeds (200)."""
    from datetime import datetime, timedelta, timezone
    from app.db.models import EmailVerificationToken
    from app.main import app

    app, session_factory = register_app
    email = _unique_email()
    password = "ValidPass1!"

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        r = await c.post(
            "/api/v1/auth/signup",
            json={"email": email, "password": password, "full_name": "Verify User"},
        )
        assert r.status_code == 201

        # Pull the generated token out of the DB (signup creates it)
        async with session_factory() as session:
            from app.db.models import User
            user_result = await session.execute(
                select(User).where(User.email == email.lower())
            )
            user = user_result.scalar_one()
            token_result = await session.execute(
                select(EmailVerificationToken).where(
                    EmailVerificationToken.user_id == user.id
                )
            )
            evt = token_result.scalar_one()
            token = evt.token

        r_verify = await c.post(
            "/api/v1/auth/verify-email",
            json={"token": token},
        )
        assert r_verify.status_code == 200, r_verify.text

        # Now login should succeed
        r_login = await c.post(
            "/api/v1/auth/login",
            json={"email": email, "password": password},
        )
        assert r_login.status_code == 200, r_login.text
        assert "access_token" in r_login.json()


@pytest.mark.asyncio
async def test_verify_email_invalid_token(register_app):
    """Verify with a bogus token returns 400."""
    app, _ = register_app

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        r = await c.post(
            "/api/v1/auth/verify-email",
            json={"token": "this-token-does-not-exist-anywhere"},
        )
        assert r.status_code == 400, r.text
        assert "Invalid" in r.json()["detail"]


@pytest.mark.asyncio
async def test_verify_email_expired(register_app):
    """An expired token returns 400."""
    from datetime import datetime, timedelta, timezone
    from app.db.models import EmailVerificationToken, User
    from app.main import app

    app, session_factory = register_app
    email = _unique_email()

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        r = await c.post(
            "/api/v1/auth/signup",
            json={"email": email, "password": "ValidPass1!", "full_name": "Expire Test"},
        )
        assert r.status_code == 201

    # Backdate the token in the DB to make it expired
    async with session_factory() as session:
        user_result = await session.execute(
            select(User).where(User.email == email.lower())
        )
        user = user_result.scalar_one()
        token_result = await session.execute(
            select(EmailVerificationToken).where(
                EmailVerificationToken.user_id == user.id
            )
        )
        evt = token_result.scalar_one()
        evt.expires_at = datetime.now(timezone.utc) - timedelta(hours=1)
        await session.commit()
        token = evt.token

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        r = await c.post(
            "/api/v1/auth/verify-email",
            json={"token": token},
        )
        assert r.status_code == 400, r.text
        assert "expired" in r.json()["detail"].lower()


@pytest.mark.asyncio
async def test_verify_email_already_used(register_app):
    """A token that has already been used returns 400."""
    from app.db.models import EmailVerificationToken, User
    from datetime import datetime, timezone
    from app.main import app

    app, session_factory = register_app
    email = _unique_email()

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        r = await c.post(
            "/api/v1/auth/signup",
            json={"email": email, "password": "ValidPass1!", "full_name": "Reuse Test"},
        )
        assert r.status_code == 201

    async with session_factory() as session:
        user_result = await session.execute(
            select(User).where(User.email == email.lower())
        )
        user = user_result.scalar_one()
        token_result = await session.execute(
            select(EmailVerificationToken).where(
                EmailVerificationToken.user_id == user.id
            )
        )
        evt = token_result.scalar_one()
        evt.used_at = datetime.now(timezone.utc)
        await session.commit()
        token = evt.token

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        r = await c.post(
            "/api/v1/auth/verify-email",
            json={"token": token},
        )
        assert r.status_code == 400, r.text
        assert "Invalid" in r.json()["detail"]
