"""
Tests for POST /v1/auth/forgot-password and /v1/auth/reset-password — US-1.3.

Acceptance Criteria (ClickUp US-1.3):
  AC1 — Submit registered email → a reset token is created, valid for the
        configured window (60 min in this build), one-time use.
  AC2 — Used or expired link → reset is rejected with an "expired / invalid"
        error (the FE renders this as "Link expired" + re-send CTA).
  AC3 — Response is identical whether the email exists or not (anti-enumeration).

Mirrors the fixture style of test_register.py: SQLite in-memory, no real
Redis/SMTP. SMTP is skipped automatically because the test Settings have no
smtp_user configured (see backend/tests/conftest.py).
"""
from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone
from typing import AsyncGenerator
from unittest.mock import AsyncMock, MagicMock

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

TEST_DB_URL = "sqlite+aiosqlite:///:memory:"

RESET_MESSAGE = "If an account with that email exists, a reset link has been sent."


# ---------------------------------------------------------------------------
# Stateful fake Redis (cooldown + lockout live here)
# ---------------------------------------------------------------------------
class _FakePipeline:
    def __init__(self, store: dict) -> None:
        self._store = store
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
                self._store[op[1]] = int(self._store.get(op[1], 0)) + 1
                results.append(self._store[op[1]])
            else:
                results.append(True)
        self._ops.clear()
        return results


class _FakeRedis:
    """Minimal stateful Redis covering get/setex/delete/ttl/pipeline."""

    def __init__(self) -> None:
        self.store: dict = {}

    async def get(self, key: str):
        return self.store.get(key)

    async def setex(self, key: str, ttl: int, value) -> None:
        self.store[key] = value

    async def delete(self, *keys: str) -> None:
        for k in keys:
            self.store.pop(k, None)

    async def ttl(self, key: str) -> int:
        return 60 if key in self.store else -2

    async def aclose(self) -> None:  # pragma: no cover
        pass

    def pipeline(self):
        return _FakePipeline(self.store)


# ---------------------------------------------------------------------------
# Fixture: isolated app + SQLite DB + fake Redis
# ---------------------------------------------------------------------------
@pytest_asyncio.fixture
async def forgot_app(tmp_path):
    from app.db.models import Base
    from app.db.session import get_session
    from app.api.deps import get_arq_pool, get_settings
    from app.main import app

    engine = create_async_engine(TEST_DB_URL, echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    session_factory = async_sessionmaker(engine, expire_on_commit=False)

    mock_arq = AsyncMock()
    fake_redis = _FakeRedis()

    mock_settings = MagicMock()
    mock_settings.database_url = MagicMock(get_secret_value=lambda: TEST_DB_URL)
    mock_settings.redis_url = "redis://localhost:6379/0"
    mock_settings.data_dir = str(tmp_path)
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
    mock_settings.forgot_password_cooldown_seconds = 60
    mock_settings.app_url = "http://localhost:8080"

    app.state.settings = mock_settings
    app.state.arq_pool = mock_arq
    app.state.redis = fake_redis
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
    return f"reset-{uuid.uuid4().hex[:8]}@example.com"


async def _create_verified_user(session_factory, email: str, password: str):
    """Insert an active, email-verified user directly (bypasses signup flow)."""
    from app.db.models import User
    from app.core.security import hash_password

    async with session_factory() as session:
        user = User(
            id=str(uuid.uuid4()),
            email=email.lower(),
            hashed_password=hash_password(password),
            full_name="Reset Test",
            is_active=True,
            is_superuser=False,
            email_verified=True,
        )
        session.add(user)
        await session.commit()
        return user.id


async def _latest_token(session_factory, user_id: str):
    from app.db.models import PasswordResetToken

    async with session_factory() as session:
        result = await session.execute(
            select(PasswordResetToken)
            .where(PasswordResetToken.user_id == user_id)
            .order_by(PasswordResetToken.created_at.desc())
        )
        return result.scalars().first()


# ===========================================================================
# AC1 — registered email creates a one-time token valid ~60 minutes
# ===========================================================================
@pytest.mark.asyncio
async def test_forgot_password_creates_token_valid_60min(forgot_app):
    app, session_factory = forgot_app
    email = _unique_email()
    user_id = await _create_verified_user(session_factory, email, "OldPass1!")

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        r = await c.post("/v1/auth/forgot-password", json={"email": email})

    assert r.status_code == 200, r.text
    assert r.json()["message"] == RESET_MESSAGE

    prt = await _latest_token(session_factory, user_id)
    assert prt is not None, "A reset token should be created for a registered email"
    assert prt.used_at is None

    # Valid for ~60 min (allow a small clock window).
    # SQLite drops tz info on round-trip; normalise to UTC-aware like the app does.
    expires_at = prt.expires_at
    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=timezone.utc)
    remaining = expires_at - datetime.now(timezone.utc)
    assert timedelta(minutes=58) < remaining <= timedelta(minutes=61), remaining


# ===========================================================================
# AC3 — anti-enumeration: identical response, no token for unknown email
# ===========================================================================
@pytest.mark.asyncio
async def test_forgot_password_anti_enumeration(forgot_app):
    app, session_factory = forgot_app
    known = _unique_email()
    await _create_verified_user(session_factory, known, "OldPass1!")
    unknown = _unique_email()

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        r_known = await c.post("/v1/auth/forgot-password", json={"email": known})
        r_unknown = await c.post("/v1/auth/forgot-password", json={"email": unknown})

    # Identical status + body whether the account exists or not.
    assert r_known.status_code == 200 == r_unknown.status_code
    assert r_known.json() == r_unknown.json()
    assert r_known.json()["message"] == RESET_MESSAGE

    # No reset token is ever created for a non-existent email.
    from app.db.models import PasswordResetToken, User

    async with session_factory() as session:
        unknown_user = (
            await session.execute(select(User).where(User.email == unknown.lower()))
        ).scalar_one_or_none()
        assert unknown_user is None
        total_tokens = (
            await session.execute(select(func.count()).select_from(PasswordResetToken))
        ).scalar_one()
        assert total_tokens == 1, "Only the known user's token should exist"


# ===========================================================================
# AC1 (happy path) — reset succeeds, new password works, old one fails
# ===========================================================================
@pytest.mark.asyncio
async def test_reset_password_full_flow(forgot_app):
    app, session_factory = forgot_app
    email = _unique_email()
    user_id = await _create_verified_user(session_factory, email, "OldPass1!")

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        r_forgot = await c.post("/v1/auth/forgot-password", json={"email": email})
        assert r_forgot.status_code == 200

        token = (await _latest_token(session_factory, user_id)).token

        r_reset = await c.post(
            "/v1/auth/reset-password",
            json={"token": token, "new_password": "BrandNew1!"},
        )
        assert r_reset.status_code == 200, r_reset.text

        # New password logs in.
        r_new = await c.post(
            "/v1/auth/login", json={"email": email, "password": "BrandNew1!"}
        )
        assert r_new.status_code == 200, r_new.text
        assert "access_token" in r_new.json()

        # Old password no longer works.
        r_old = await c.post(
            "/v1/auth/login", json={"email": email, "password": "OldPass1!"}
        )
        assert r_old.status_code == 401, r_old.text

    # Token is consumed (one-time use).
    prt = await _latest_token(session_factory, user_id)
    assert prt.used_at is not None


# ===========================================================================
# AC2 — a used token is rejected
# ===========================================================================
@pytest.mark.asyncio
async def test_reset_password_used_token_rejected(forgot_app):
    app, session_factory = forgot_app
    email = _unique_email()
    user_id = await _create_verified_user(session_factory, email, "OldPass1!")

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        await c.post("/v1/auth/forgot-password", json={"email": email})
        token = (await _latest_token(session_factory, user_id)).token

        r1 = await c.post(
            "/v1/auth/reset-password",
            json={"token": token, "new_password": "BrandNew1!"},
        )
        assert r1.status_code == 200, r1.text

        # Reusing the same token must fail.
        r2 = await c.post(
            "/v1/auth/reset-password",
            json={"token": token, "new_password": "Another1!"},
        )
        assert r2.status_code == 400, r2.text
        assert "expired" in r2.json()["detail"].lower() or "invalid" in r2.json()["detail"].lower()


# ===========================================================================
# AC2 — an expired token is rejected with an "expired" error
# ===========================================================================
@pytest.mark.asyncio
async def test_reset_password_expired_token_rejected(forgot_app):
    from app.db.models import PasswordResetToken

    app, session_factory = forgot_app
    email = _unique_email()
    user_id = await _create_verified_user(session_factory, email, "OldPass1!")

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        await c.post("/v1/auth/forgot-password", json={"email": email})

    # Backdate the token so it is expired.
    async with session_factory() as session:
        prt = (
            await session.execute(
                select(PasswordResetToken).where(PasswordResetToken.user_id == user_id)
            )
        ).scalar_one()
        prt.expires_at = datetime.now(timezone.utc) - timedelta(minutes=1)
        await session.commit()
        token = prt.token

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        r = await c.post(
            "/v1/auth/reset-password",
            json={"token": token, "new_password": "BrandNew1!"},
        )
    assert r.status_code == 400, r.text
    assert "expired" in r.json()["detail"].lower()


# ===========================================================================
# AC2 — an unknown/garbage token is rejected
# ===========================================================================
@pytest.mark.asyncio
async def test_reset_password_invalid_token_rejected(forgot_app):
    app, _ = forgot_app
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        r = await c.post(
            "/v1/auth/reset-password",
            json={"token": "not-a-real-token-anywhere", "new_password": "BrandNew1!"},
        )
    assert r.status_code == 400, r.text
    assert "invalid" in r.json()["detail"].lower() or "expired" in r.json()["detail"].lower()


# ===========================================================================
# Anti-spam — a 2nd request inside the cooldown does not mint a 2nd token
# ===========================================================================
@pytest.mark.asyncio
async def test_forgot_password_cooldown_no_second_token(forgot_app):
    from app.db.models import PasswordResetToken

    app, session_factory = forgot_app
    email = _unique_email()
    user_id = await _create_verified_user(session_factory, email, "OldPass1!")

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        r1 = await c.post("/v1/auth/forgot-password", json={"email": email})
        r2 = await c.post("/v1/auth/forgot-password", json={"email": email})

    assert r1.status_code == 200 and r2.status_code == 200
    assert r1.json() == r2.json()  # identical response (still anti-enumeration safe)

    async with session_factory() as session:
        count = (
            await session.execute(
                select(func.count())
                .select_from(PasswordResetToken)
                .where(PasswordResetToken.user_id == user_id)
            )
        ).scalar_one()
    assert count == 1, "Cooldown should prevent a second token within the window"
