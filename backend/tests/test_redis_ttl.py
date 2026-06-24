"""Tests for TASK-4.1 — Redis TTL accuracy after activation.

Verification command (featurelist.json 4.1-c):
  cd backend && uv run pytest -o addopts="" tests/test_redis_ttl.py -k ttl_within_two_seconds -q

Covers:
- ttl_within_two_seconds: after activate, license:{key_hash} TTL == (expired_at - now) ± 2s
- cache-miss repopulation: clear the key, hit the middleware, verify key is repopulated with
  TTL > 0 and endpoint returns 200.
"""
from __future__ import annotations

import json
import uuid
from datetime import datetime, timedelta, timezone
from typing import AsyncGenerator
from unittest.mock import MagicMock, patch

import fakeredis.aioredis as fakeredis_async
import pytest
import pytest_asyncio
from fastapi import FastAPI
from fastapi.responses import JSONResponse
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

TEST_DB_URL = "sqlite+aiosqlite:///:memory:"


# ---------------------------------------------------------------------------
# Minimal test app (same helper as test_time_travel_expiry)
# ---------------------------------------------------------------------------

def _make_test_app(engine, fake_redis):
    from app.api.middleware.license import LicenseValidationMiddleware

    test_app = FastAPI()

    @test_app.get("/api/v1/ping")
    async def ping():
        return JSONResponse({"ok": True})

    test_app.add_middleware(LicenseValidationMiddleware)
    test_app.state.redis = fake_redis
    test_app.state.engine = engine
    return test_app


# ---------------------------------------------------------------------------
# Fixtures — mirror test_activate.py pattern (self-contained per test)
# ---------------------------------------------------------------------------

@pytest_asyncio.fixture
async def ttl_app(tmp_path):
    """Yield (http_app, activate_app, session_factory, fake_redis) for TTL tests.

    activate_app is the real FastAPI app (with activate endpoint).
    http_app is a minimal stub that goes through LicenseValidationMiddleware.
    Both share the same engine + fakeredis.
    """
    from app.db.models import Base
    from app.db.session import get_session
    from app.api.deps import get_arq_pool, get_settings, get_redis
    from app.main import app as main_app

    engine = create_async_engine(TEST_DB_URL, echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    session_factory = async_sessionmaker(engine, expire_on_commit=False)

    fake_server = fakeredis_async.FakeRedis(decode_responses=True)

    mock_arq = MagicMock()
    mock_settings = MagicMock()
    mock_settings.database_url = MagicMock(get_secret_value=lambda: TEST_DB_URL)
    mock_settings.redis_url = "redis://localhost:6379/0"
    mock_settings.data_dir = str(tmp_path)
    mock_settings.license_signing_secret = MagicMock(
        get_secret_value=lambda: "test-license-signing-secret-placeholder"
    )

    main_app.state.settings = mock_settings
    main_app.state.arq_pool = mock_arq
    main_app.state.redis = fake_server
    main_app.state.engine = engine

    async def override_get_session() -> AsyncGenerator[AsyncSession, None]:
        async with session_factory() as session:
            yield session

    def override_get_arq_pool(request=None):
        return mock_arq

    def override_get_settings(request=None):
        return mock_settings

    def override_get_redis(request=None):
        return fake_server

    main_app.dependency_overrides[get_session] = override_get_session
    main_app.dependency_overrides[get_arq_pool] = override_get_arq_pool
    main_app.dependency_overrides[get_settings] = override_get_settings
    main_app.dependency_overrides[get_redis] = override_get_redis

    # Minimal app that runs through LicenseValidationMiddleware
    middleware_app = _make_test_app(engine, fake_server)

    yield main_app, middleware_app, session_factory, fake_server

    main_app.dependency_overrides.clear()
    for attr in ("settings", "arq_pool", "redis", "engine"):
        try:
            delattr(main_app.state, attr)
        except AttributeError:
            pass
    await fake_server.aclose()
    await engine.dispose()


async def _make_user(session_factory):
    from app.db.models import User
    from app.core.security import hash_password

    async with session_factory() as session:
        user = User(
            id=str(uuid.uuid4()),
            email=f"user-{uuid.uuid4().hex[:8]}@test.com",
            hashed_password=hash_password("Password1!"),
            is_active=True,
            is_superuser=False,
        )
        session.add(user)
        await session.commit()
        await session.refresh(user)
        return user


async def _make_pending_license(
    session_factory,
    *,
    customer_id: str,
    expired_at: datetime | None = None,
) -> tuple[str, str]:
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
            expired_at=expired_at,
        )
        session.add(lic)
        await session.commit()
        await session.refresh(lic)
        return lic.id, raw_key


# ---------------------------------------------------------------------------
# 4.1-c: ttl_within_two_seconds
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_ttl_within_two_seconds(ttl_app):
    """After activation, TTL of license:{key_hash} is within ±2s of (expired_at - now).

    Uses a fixed expired_at so expected TTL is deterministic.
    """
    from app.licensing.keygen import hash_key

    activate_app, _middleware_app, session_factory, fake_redis = ttl_app

    customer = await _make_user(session_factory)

    # Fixed expiry in the future: gives a predictable TTL
    fixed_expiry = datetime.now(timezone.utc) + timedelta(days=30)
    _lic_id, raw_key = await _make_pending_license(
        session_factory, customer_id=customer.id, expired_at=fixed_expiry
    )

    before = datetime.now(timezone.utc)

    async with AsyncClient(
        transport=ASGITransport(app=activate_app), base_url="http://test"
    ) as c:
        r = await c.post("/licenses/activate", json={"raw_key": raw_key})
        assert r.status_code == 200, f"Activation failed: {r.text}"

    after = datetime.now(timezone.utc)

    kh = hash_key(raw_key)
    cache_key = f"license:{kh}"

    ttl = await fake_redis.ttl(cache_key)
    assert ttl > 0, f"Expected positive TTL, got {ttl}"

    # Expected TTL = (fixed_expiry - activation_time)
    # Bound: [fixed_expiry - after - 2, fixed_expiry - before + 2]
    expected_lower = int((fixed_expiry - after).total_seconds()) - 2
    expected_upper = int((fixed_expiry - before).total_seconds()) + 2

    assert expected_lower <= ttl <= expected_upper, (
        f"TTL {ttl}s not within ±2s of expected "
        f"[{expected_lower}, {expected_upper}]. "
        f"fixed_expiry={fixed_expiry.isoformat()}, "
        f"before={before.isoformat()}, after={after.isoformat()}"
    )

    # Cache value must be valid JSON with correct status
    raw_val = await fake_redis.get(cache_key)
    assert raw_val is not None, "Cache key missing after activation"
    cached = json.loads(raw_val)
    assert cached["status"] == "ACTIVE"
    assert cached["expired_at"] is not None


@pytest.mark.asyncio
async def test_ttl_within_two_seconds_cache_miss_repopulates(ttl_app):
    """Cache-miss path: clearing the Redis key forces middleware to repopulate it.

    Flow:
    1. Activate license (populates cache).
    2. DEL the cache key (simulate eviction / expiry of the cache entry itself).
    3. Hit /api/v1/ping with the license key header.
    4. Assert: middleware repopulated the key (TTL > 0) and returned 200.
    """
    from app.licensing.keygen import hash_key

    activate_app, middleware_app, session_factory, fake_redis = ttl_app

    customer = await _make_user(session_factory)
    fixed_expiry = datetime.now(timezone.utc) + timedelta(days=15)
    _lic_id, raw_key = await _make_pending_license(
        session_factory, customer_id=customer.id, expired_at=fixed_expiry
    )

    # Step 1: activate
    async with AsyncClient(
        transport=ASGITransport(app=activate_app), base_url="http://test"
    ) as c:
        r = await c.post("/licenses/activate", json={"raw_key": raw_key})
        assert r.status_code == 200, f"Activation failed: {r.text}"

    kh = hash_key(raw_key)
    cache_key = f"license:{kh}"

    # Step 2: simulate cache eviction
    await fake_redis.delete(cache_key)
    assert await fake_redis.get(cache_key) is None, "Key should be absent after DEL"

    # Step 3: hit the middleware — triggers DB-miss repopulation path
    async with AsyncClient(
        transport=ASGITransport(app=middleware_app), base_url="http://test"
    ) as c:
        r = await c.get("/api/v1/ping", headers={"X-License-Key": raw_key})

    # Step 4: verify
    assert r.status_code == 200, (
        f"Expected 200 after cache-miss repopulation, got {r.status_code}: {r.text}"
    )

    repopulated_ttl = await fake_redis.ttl(cache_key)
    assert repopulated_ttl > 0, (
        f"Cache key was not repopulated (TTL={repopulated_ttl})"
    )

    # Value is valid JSON with ACTIVE status
    raw_val = await fake_redis.get(cache_key)
    assert raw_val is not None
    cached = json.loads(raw_val)
    assert cached["status"] == "ACTIVE", f"Unexpected status in repopulated cache: {cached}"
