"""
Tests for LicenseValidationMiddleware — TASK-2.3.

Covers behaviors:
- 2.3-a: active_key_passes        — valid ACTIVE key in X-License-Key passes through
- 2.3-b: invalid_key_403_body     — missing/invalid/expired key → 403 {"error":"LICENSE_INVALID","code":"E4030"}
- 2.3-c: cache_miss_repopulate    — MISS → DB query → Redis repopulated with TTL > 0
- 2.3-d: excludes_admin_and_activate — /admin/** and /licenses/activate bypass middleware

Uses:
- SQLite in-memory DB (same pattern as test_activate.py)
- fakeredis.aioredis (real NX/EX/TTL semantics, no live Redis required)
- A throwaway test route mounted under /v1/ping via dependency_overrides trick
"""
from __future__ import annotations

import json
import uuid
from datetime import datetime, timedelta, timezone

import fakeredis.aioredis as fakeredis_async
import pytest
import pytest_asyncio
from fastapi import FastAPI
from fastapi.routing import APIRoute
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

TEST_DB_URL = "sqlite+aiosqlite:///:memory:"


# ---------------------------------------------------------------------------
# Helpers — DB seeding
# ---------------------------------------------------------------------------

async def _make_user(session_factory) -> "User":  # noqa: F821
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


async def _make_active_license(
    session_factory,
    *,
    customer_id: str,
    expired_at: datetime | None = None,
) -> tuple[str, str]:
    """Insert an ACTIVE license. Returns (license_id, raw_key)."""
    from app.db.models import License, LicenseStatus, LicenseTier
    from app.licensing.keygen import generate_license_key, hash_key

    raw_key = generate_license_key("test-license-signing-secret-placeholder", customer_id)
    kh = hash_key(raw_key)
    now = datetime.now(timezone.utc)
    exp = expired_at or (now + timedelta(days=365))

    async with session_factory() as session:
        lic = License(
            id=str(uuid.uuid4()),
            key_hash=kh,
            tier=LicenseTier.PRO,
            status=LicenseStatus.ACTIVE,
            customer_id=customer_id,
            max_devices=1,
            activated_at=now,
            expired_at=exp,
        )
        session.add(lic)
        await session.commit()
        await session.refresh(lic)
        return lic.id, raw_key


# ---------------------------------------------------------------------------
# Fixture: builds a minimal FastAPI app with LicenseValidationMiddleware
# and a /v1/ping test route.
# ---------------------------------------------------------------------------

@pytest_asyncio.fixture
async def middleware_app(tmp_path):
    """
    Yield (app, session_factory, fake_redis).

    The app includes:
    - LicenseValidationMiddleware
    - GET /v1/ping (returns 200 {"pong": true})
    - GET /admin/whatever (returns 200 — must NOT be blocked)
    - POST /licenses/activate stub (returns 200 — must NOT be blocked)

    app.state.redis and app.state.engine are set to fake instances so the
    middleware's direct app.state access works without a full lifespan.
    """
    from app.db.models import Base
    from app.api.middleware.license import LicenseValidationMiddleware

    # --- DB ------------------------------------------------------------------
    engine = create_async_engine(TEST_DB_URL, echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    session_factory = async_sessionmaker(engine, expire_on_commit=False)

    # --- fakeredis -----------------------------------------------------------
    fake_redis = fakeredis_async.FakeRedis(decode_responses=True)

    # --- build minimal app ---------------------------------------------------
    app = FastAPI()

    @app.get("/v1/ping")
    async def ping():
        return {"pong": True}

    @app.get("/admin/whatever")
    async def admin_whatever():
        return {"admin": True}

    @app.post("/licenses/activate")
    async def activate_stub():
        return {"activated": True}

    # Middleware is added AFTER routes are defined (Starlette wraps inward)
    app.add_middleware(LicenseValidationMiddleware)

    # Wire app.state so middleware's direct state access works
    app.state.engine = engine
    app.state.redis = fake_redis

    yield app, session_factory, fake_redis

    await fake_redis.aclose()
    await engine.dispose()


# ---------------------------------------------------------------------------
# 2.3-a: active_key_passes
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_active_key_passes(middleware_app):
    """
    Valid ACTIVE license in Redis cache → GET /v1/ping returns 200.
    """
    from app.licensing.keygen import hash_key

    app, session_factory, fake_redis = middleware_app

    user = await _make_user(session_factory)
    _lid, raw_key = await _make_active_license(session_factory, customer_id=user.id)

    # Pre-populate Redis cache (simulates what activation does)
    kh = hash_key(raw_key)
    cache_key = f"license:{kh}"
    exp = (datetime.now(timezone.utc) + timedelta(days=365)).isoformat()
    cache_payload = json.dumps({
        "id": _lid,
        "tier": "PRO",
        "status": "ACTIVE",
        "activated_at": datetime.now(timezone.utc).isoformat(),
        "expired_at": exp,
    })
    await fake_redis.set(cache_key, cache_payload, ex=86400)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        r = await c.get("/v1/ping", headers={"X-License-Key": raw_key})

    assert r.status_code == 200, r.text
    assert r.json() == {"pong": True}


# ---------------------------------------------------------------------------
# 2.3-b: invalid_key_403_body
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_invalid_key_403_body_missing_header(middleware_app):
    """Missing X-License-Key on /api/v1/** → 403 with exact body."""
    app, _sf, _redis = middleware_app

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        r = await c.get("/v1/ping")  # no header

    assert r.status_code == 403
    assert r.json() == {"error": "LICENSE_INVALID", "code": "E4030"}


@pytest.mark.asyncio
async def test_invalid_key_403_body_unknown_key(middleware_app):
    """Unknown key (no DB row, no cache) → 403 with exact body."""
    app, _sf, _redis = middleware_app

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        r = await c.get("/v1/ping", headers={"X-License-Key": "FAKE-FAKE-FAKE-FAKE"})

    assert r.status_code == 403
    assert r.json() == {"error": "LICENSE_INVALID", "code": "E4030"}


@pytest.mark.asyncio
async def test_invalid_key_403_body_expired_license(middleware_app):
    """Expired license in Redis cache → 403 with exact body."""
    from app.licensing.keygen import hash_key

    app, session_factory, fake_redis = middleware_app

    user = await _make_user(session_factory)
    _lid, raw_key = await _make_active_license(session_factory, customer_id=user.id)

    # Put an expired entry in cache
    kh = hash_key(raw_key)
    cache_key = f"license:{kh}"
    expired_at = (datetime.now(timezone.utc) - timedelta(seconds=1)).isoformat()
    cache_payload = json.dumps({
        "id": _lid,
        "tier": "PRO",
        "status": "ACTIVE",
        "activated_at": datetime.now(timezone.utc).isoformat(),
        "expired_at": expired_at,
    })
    await fake_redis.set(cache_key, cache_payload, ex=1)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        r = await c.get("/v1/ping", headers={"X-License-Key": raw_key})

    assert r.status_code == 403
    assert r.json() == {"error": "LICENSE_INVALID", "code": "E4030"}


# ---------------------------------------------------------------------------
# 2.3-c: cache_miss_repopulate
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_cache_miss_repopulate(middleware_app):
    """
    ACTIVE license in DB but NO Redis entry:
    - Request succeeds (200)
    - Redis now contains license:{hash} with TTL > 0
    """
    from app.licensing.keygen import hash_key

    app, session_factory, fake_redis = middleware_app

    user = await _make_user(session_factory)
    _lid, raw_key = await _make_active_license(session_factory, customer_id=user.id)

    kh = hash_key(raw_key)
    cache_key = f"license:{kh}"

    # Confirm cache is empty before the request
    assert await fake_redis.get(cache_key) is None, "Pre-condition: cache should be empty"

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        r = await c.get("/v1/ping", headers={"X-License-Key": raw_key})

    assert r.status_code == 200, r.text

    # Cache must be populated with a positive TTL
    ttl = await fake_redis.ttl(cache_key)
    assert ttl > 0, f"Expected positive TTL after repopulate, got {ttl}"

    raw_val = await fake_redis.get(cache_key)
    assert raw_val is not None
    cached = json.loads(raw_val)
    assert cached["status"] == "ACTIVE"
    assert cached["id"] == _lid


# ---------------------------------------------------------------------------
# 2.3-d: excludes_admin_and_activate
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_excludes_admin_and_activate(middleware_app):
    """
    /api/admin/** and /licenses/activate are NOT blocked by LicenseValidationMiddleware
    even when no X-License-Key header is sent.
    """
    app, _sf, _redis = middleware_app

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        # Admin route — must pass through (200, not 403)
        r_admin = await c.get("/admin/whatever")
        assert r_admin.status_code == 200, (
            f"Admin route was blocked by license middleware: {r_admin.status_code}"
        )

        # Activate endpoint — must pass through (200, not 403)
        r_activate = await c.post("/licenses/activate")
        assert r_activate.status_code == 200, (
            f"Activate route was blocked by license middleware: {r_activate.status_code}"
        )
