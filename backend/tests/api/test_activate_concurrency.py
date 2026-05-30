"""
Concurrency tests for POST /licenses/activate — TASK-2.2 behavior 2.2-b.

- only_one_wins: N concurrent activations of one key → exactly one 200, the rest 409
"""
from __future__ import annotations

import asyncio
import uuid
from typing import AsyncGenerator

import fakeredis.aioredis as fakeredis_async
import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

TEST_DB_URL = "sqlite+aiosqlite:///:memory:"


# ---------------------------------------------------------------------------
# Fixture
# ---------------------------------------------------------------------------

@pytest_asyncio.fixture
async def concurrency_app(tmp_path):
    """
    Yield (app, session_factory, fake_redis) for concurrency testing.
    All concurrent requests share the SAME fakeredis instance so NX
    lock semantics are honoured.
    """
    from app.db.models import Base
    from app.db.session import get_session
    from app.api.deps import get_arq_pool, get_settings, get_redis
    from app.main import app

    engine = create_async_engine(TEST_DB_URL, echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    session_factory = async_sessionmaker(engine, expire_on_commit=False)

    # ONE shared fakeredis instance — all concurrent requests hit the same "server".
    # decode_responses=True matches production Redis client (main.py uses decode_responses=True).
    fake_server = fakeredis_async.FakeRedis(decode_responses=True)

    from unittest.mock import MagicMock

    mock_arq = MagicMock()
    mock_settings = MagicMock()
    mock_settings.database_url = MagicMock(get_secret_value=lambda: TEST_DB_URL)
    mock_settings.redis_url = "redis://localhost:6379/0"
    mock_settings.data_dir = str(tmp_path)
    mock_settings.license_signing_secret = MagicMock(
        get_secret_value=lambda: "test-license-signing-secret-placeholder"
    )

    app.state.settings = mock_settings
    app.state.arq_pool = mock_arq
    app.state.redis = fake_server
    app.state.engine = engine

    async def override_get_session() -> AsyncGenerator[AsyncSession, None]:
        async with session_factory() as session:
            yield session

    def override_get_arq_pool(request=None):
        return mock_arq

    def override_get_settings(request=None):
        return mock_settings

    def override_get_redis(request=None):
        return fake_server

    app.dependency_overrides[get_session] = override_get_session
    app.dependency_overrides[get_arq_pool] = override_get_arq_pool
    app.dependency_overrides[get_settings] = override_get_settings
    app.dependency_overrides[get_redis] = override_get_redis

    yield app, session_factory, fake_server

    app.dependency_overrides.clear()
    for attr in ("settings", "arq_pool", "redis", "engine"):
        try:
            delattr(app.state, attr)
        except AttributeError:
            pass
    await fake_server.aclose()
    await engine.dispose()


async def _make_user(session_factory, *, is_superuser: bool = False):
    from app.db.models import User
    from app.core.security import hash_password

    async with session_factory() as session:
        user = User(
            id=str(uuid.uuid4()),
            email=f"user-{uuid.uuid4().hex[:8]}@test.com",
            hashed_password=hash_password("Password1!"),
            is_active=True,
            is_superuser=is_superuser,
        )
        session.add(user)
        await session.commit()
        await session.refresh(user)
        return user


async def _make_pending_license(session_factory, *, customer_id: str) -> tuple[str, str]:
    """Insert a PENDING license. Returns (license_id, raw_key)."""
    from app.db.models import License, LicenseStatus, LicenseTier
    from app.licensing.keygen import generate_license_key, hash_key

    raw_key = generate_license_key("test-license-signing-secret-placeholder", customer_id)
    kh = hash_key(raw_key)

    async with session_factory() as session:
        lic = License(
            id=str(uuid.uuid4()),
            key_hash=kh,
            tier=LicenseTier.PRO,
            status=LicenseStatus.PENDING,
            customer_id=customer_id,
            max_devices=1,
        )
        session.add(lic)
        await session.commit()
        await session.refresh(lic)
        return lic.id, raw_key


# ---------------------------------------------------------------------------
# 2.2-b: only_one_wins
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_only_one_wins(concurrency_app):
    """
    N concurrent activation requests for the same key:
    - Exactly one returns 200 (ACTIVE)
    - All others return 409 (lock contended) or 400 (already activated)

    Deterministic because all coroutines share ONE fakeredis instance that
    implements real NX semantics — only one SET NX can succeed.
    """
    N = 8  # concurrent callers
    app, session_factory, fake_redis = concurrency_app

    customer = await _make_user(session_factory)
    _license_id, raw_key = await _make_pending_license(
        session_factory, customer_id=customer.id
    )

    async def _activate():
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as c:
            r = await c.post("/licenses/activate", json={"raw_key": raw_key})
            return r.status_code

    results = await asyncio.gather(*[_activate() for _ in range(N)])

    successes = [s for s in results if s == 200]
    failures = [s for s in results if s in (409, 400)]

    assert len(successes) == 1, (
        f"Expected exactly 1 success, got {len(successes)}. All statuses: {results}"
    )
    assert len(failures) == N - 1, (
        f"Expected {N - 1} failures (409/400), got {len(failures)}. All statuses: {results}"
    )


# ---------------------------------------------------------------------------
# 4.1-a: twenty_workers_one_winner
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_twenty_workers_one_winner(concurrency_app):
    """
    20 concurrent activation requests for the same key:
    - Exactly one returns 200 (ACTIVE).
    - All 19 others return 409 (lock contended) or 400 (already activated).

    Deterministic: all coroutines share ONE fakeredis so NX lock semantics
    are real — only one SET NX wins, the rest are rejected immediately.
    No sleeps or timing-dependent assertions.
    """
    N = 20
    app, session_factory, fake_redis = concurrency_app

    customer = await _make_user(session_factory)
    _license_id, raw_key = await _make_pending_license(
        session_factory, customer_id=customer.id
    )

    async def _activate():
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as c:
            r = await c.post("/licenses/activate", json={"raw_key": raw_key})
            return r.status_code

    results = await asyncio.gather(*[_activate() for _ in range(N)])

    successes = [s for s in results if s == 200]
    failures = [s for s in results if s in (409, 400)]

    assert len(successes) == 1, (
        f"Expected exactly 1 success (200), got {len(successes)}. "
        f"All statuses: {sorted(results)}"
    )
    assert len(failures) == N - 1, (
        f"Expected {N - 1} failures (409/400), got {len(failures)}. "
        f"All statuses: {sorted(results)}"
    )
