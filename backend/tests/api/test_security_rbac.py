"""
TASK-4.2-b: RBAC — regular (non-admin) user calling admin endpoint gets 403.

Verification command:
    cd backend && uv run pytest -o addopts="" tests/api -k rbac_regular_user_forbidden -q

The test builds a non-admin user + real JWT, POSTs to POST /admin/licenses,
and asserts 403.  No dependency overrides for require_admin — the real RBAC
chain (get_current_user → get_current_active_user → require_admin) runs fully.
"""
from __future__ import annotations

import uuid
from typing import AsyncGenerator
from unittest.mock import MagicMock

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

TEST_DB_URL = "sqlite+aiosqlite:///:memory:"


# ---------------------------------------------------------------------------
# Fixtures — isolated app + SQLite, no real Redis
# ---------------------------------------------------------------------------

@pytest_asyncio.fixture
async def rbac_app(tmp_path):
    """
    App with SQLite + fakeredis; NO require_admin override — real auth chain runs.
    """
    from app.db.models import Base
    from app.db.session import get_session
    from app.api.deps import get_arq_pool, get_settings, get_redis
    from app.main import app
    import fakeredis.aioredis as fakeredis_async

    engine = create_async_engine(TEST_DB_URL, echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    session_factory = async_sessionmaker(engine, expire_on_commit=False)

    fake_redis = fakeredis_async.FakeRedis(decode_responses=True)
    mock_arq = MagicMock()
    mock_settings = MagicMock()
    mock_settings.database_url = MagicMock(get_secret_value=lambda: TEST_DB_URL)
    mock_settings.redis_url = "redis://localhost:6379/0"
    mock_settings.data_dir = str(tmp_path)
    mock_settings.license_signing_secret = MagicMock(
        get_secret_value=lambda: "rbac-test-signing-secret"
    )

    app.state.settings = mock_settings
    app.state.arq_pool = mock_arq
    app.state.redis = fake_redis
    app.state.engine = engine

    async def override_get_session() -> AsyncGenerator[AsyncSession, None]:
        async with session_factory() as session:
            yield session

    app.dependency_overrides[get_session] = override_get_session
    app.dependency_overrides[get_arq_pool] = lambda request=None: mock_arq
    app.dependency_overrides[get_settings] = lambda request=None: mock_settings
    app.dependency_overrides[get_redis] = lambda request=None: fake_redis

    yield app, session_factory

    app.dependency_overrides.clear()
    for attr in ("settings", "arq_pool", "redis", "engine"):
        try:
            delattr(app.state, attr)
        except AttributeError:
            pass
    await fake_redis.aclose()
    await engine.dispose()


async def _make_user(
    session_factory,
    *,
    is_superuser: bool = False,
    email: str | None = None,
) -> "User":  # noqa: F821
    from app.db.models import User
    from app.core.security import hash_password

    email = email or f"user-{uuid.uuid4().hex[:8]}@test.com"
    async with session_factory() as session:
        user = User(
            id=str(uuid.uuid4()),
            email=email,
            hashed_password=hash_password("Password1!"),
            is_active=True,
            is_superuser=is_superuser,
        )
        session.add(user)
        await session.commit()
        await session.refresh(user)
        return user


def _token(user_id: str) -> str:
    from app.core.security import create_access_token
    return create_access_token({"sub": user_id})


# ---------------------------------------------------------------------------
# 4.2-b: rbac_regular_user_forbidden
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_rbac_regular_user_forbidden(rbac_app):
    """
    A regular user (is_superuser=False) calling POST /admin/licenses gets 403.

    The full RBAC dependency chain runs:
        HTTPBearer → decode_access_token → get_current_user (DB lookup)
        → get_current_active_user → require_admin (checks is_superuser)

    No overrides for require_admin — this is a real end-to-end RBAC check.
    """
    app, session_factory = rbac_app

    # Create a regular (non-admin) user
    regular_user = await _make_user(session_factory, is_superuser=False)
    regular_token = _token(regular_user.id)

    create_body = {
        "tier": "PRO",
        "customer_id": str(uuid.uuid4()),
        "max_devices": 1,
    }

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        r = await client.post(
            "/admin/licenses",
            json=create_body,
            headers={"Authorization": f"Bearer {regular_token}"},
        )

    assert r.status_code == 403, (
        f"Expected 403 Forbidden for non-admin user, got {r.status_code}: {r.text}"
    )
    detail = r.json().get("detail", "")
    # The error message should clearly indicate an authorization failure
    assert detail, "403 response must include a detail message"
