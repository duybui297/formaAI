"""
Tests for POST /licenses/activate — TASK-2.2.

Covers behaviors:
- 2.2-a: first_activation_succeeds — 200 + ACTIVE + activated_at/expired_at set
- 2.2-c: already_activated_400 — activating an already-ACTIVE key → 400
- 2.2-d: cache_ttl_matches_expiry — Redis license:{hash} TTL ≈ expired_at - now
- 2.2-e: lock_released_on_exception — lock:activate:{hash} gone after exception mid-flow
"""
from __future__ import annotations

import json
import uuid
from datetime import datetime, timedelta, timezone
from typing import AsyncGenerator
from unittest.mock import AsyncMock, MagicMock, patch

import fakeredis.aioredis as fakeredis_async
import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

TEST_DB_URL = "sqlite+aiosqlite:///:memory:"


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest_asyncio.fixture
async def activate_app(tmp_path):
    """
    Yield (app, session_factory, fake_redis) with:
    - SQLite in-memory DB, all tables created
    - fakeredis.aioredis server (real NX/EX semantics, no live Redis required)
    - Dependency overrides for get_session, get_settings, get_redis
    """
    from app.db.models import Base
    from app.db.session import get_session
    from app.api.deps import get_arq_pool, get_settings, get_redis
    from app.main import app

    engine = create_async_engine(TEST_DB_URL, echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    session_factory = async_sessionmaker(engine, expire_on_commit=False)

    # fakeredis server — shared across the entire fixture; real NX/EX semantics.
    # decode_responses=True matches production Redis client (main.py uses Redis.from_url
    # with decode_responses=True) so string/bytes comparisons work identically.
    fake_server = fakeredis_async.FakeRedis(decode_responses=True)

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


async def _make_user(session_factory, *, is_superuser: bool = False) -> "User":  # noqa: F821
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


async def _make_pending_license(session_factory, *, customer_id: str, expired_at=None) -> tuple[str, str]:
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
            expired_at=expired_at,
        )
        session.add(lic)
        await session.commit()
        await session.refresh(lic)
        return lic.id, raw_key


# ---------------------------------------------------------------------------
# 2.2-a: first_activation_succeeds
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_first_activation_succeeds(activate_app):
    """
    First valid activation of a PENDING key:
    - Returns 200 with status=ACTIVE
    - activated_at is set (non-null)
    - expired_at is set (non-null)
    - DB row has status=ACTIVE
    - LicenseActivity ACTIVATED row written
    """
    app, session_factory, fake_redis = activate_app

    customer = await _make_user(session_factory)
    license_id, raw_key = await _make_pending_license(
        session_factory, customer_id=customer.id
    )

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        r = await c.post("/licenses/activate", json={"raw_key": raw_key})
        assert r.status_code == 200, r.text
        data = r.json()

    assert data["status"] == "ACTIVE"
    assert data["activated_at"] is not None
    assert data["expired_at"] is not None
    assert data["id"] == license_id
    assert data["tier"] == "PRO"

    # Verify DB state
    async with session_factory() as session:
        from app.db.models import License, LicenseActivity, LicenseStatus

        lic = await session.get(License, license_id)
        assert lic is not None
        assert lic.status == LicenseStatus.ACTIVE
        assert lic.activated_at is not None
        assert lic.expired_at is not None

        result = await session.execute(
            select(LicenseActivity).where(LicenseActivity.license_id == license_id)
        )
        activities = result.scalars().all()
        activated = [a for a in activities if a.event_type.value == "ACTIVATED"]
        assert len(activated) == 1


# ---------------------------------------------------------------------------
# 2.2-c: already_activated_400
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_already_activated_400(activate_app):
    """
    Activating an already-ACTIVE license returns 400.
    """
    app, session_factory, fake_redis = activate_app

    customer = await _make_user(session_factory)
    license_id, raw_key = await _make_pending_license(
        session_factory, customer_id=customer.id
    )

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        # First activation — must succeed
        r1 = await c.post("/licenses/activate", json={"raw_key": raw_key})
        assert r1.status_code == 200, r1.text

        # Second activation — must return 400
        r2 = await c.post("/licenses/activate", json={"raw_key": raw_key})
        assert r2.status_code == 400, r2.text
        assert "activated" in r2.json()["detail"].lower() or "status" in r2.json()["detail"].lower()


# ---------------------------------------------------------------------------
# 2.2-d: cache_ttl_matches_expiry
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_cache_ttl_matches_expiry(activate_app):
    """
    After activation, Redis key license:{key_hash} exists with TTL ≈ expired_at - now.
    Tolerance: within 5 seconds.
    """
    from app.licensing.keygen import hash_key

    app, session_factory, fake_redis = activate_app

    customer = await _make_user(session_factory)
    # Use a fixed expired_at so we can calculate expected TTL precisely
    fixed_expiry = datetime.now(timezone.utc) + timedelta(days=10)
    license_id, raw_key = await _make_pending_license(
        session_factory, customer_id=customer.id, expired_at=fixed_expiry
    )

    before = datetime.now(timezone.utc)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        r = await c.post("/licenses/activate", json={"raw_key": raw_key})
        assert r.status_code == 200, r.text

    after = datetime.now(timezone.utc)
    key_hash_value = hash_key(raw_key)
    cache_key = f"license:{key_hash_value}"

    # TTL must exist
    ttl = await fake_redis.ttl(cache_key)
    assert ttl > 0, f"Expected positive TTL, got {ttl}"

    # The expected TTL window: from when we set it until expiry
    expected_max = int((fixed_expiry - before).total_seconds())
    expected_min = int((fixed_expiry - after).total_seconds()) - 5  # 5s tolerance

    assert expected_min <= ttl <= expected_max + 5, (
        f"TTL {ttl} not within [{expected_min}, {expected_max + 5}] seconds of expected"
    )

    # Cache value must be valid JSON with expected fields
    raw_val = await fake_redis.get(cache_key)
    assert raw_val is not None
    cached = json.loads(raw_val)
    assert cached["status"] == "ACTIVE"
    assert cached["tier"] == "PRO"
    assert cached["id"] == license_id


# ---------------------------------------------------------------------------
# 2.2-e: lock_released_on_exception
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_lock_released_on_exception(activate_app):
    """
    If an exception is raised mid-activation (after the Redis lock is acquired),
    the lock key lock:activate:{key_hash} must be deleted in the finally block.

    Tested by calling activate_license() directly (not via HTTP) so the
    RuntimeError raised at commit time doesn't need an HTTP exception handler.
    The ASGI layer would absorb it anyway — this tests the service invariant.
    """
    import fakeredis.aioredis as fakeredis_async
    from app.licensing.keygen import hash_key
    from app.schemas.license import ActivateRequest
    from app.services.license_service import activate_license

    _app, session_factory, _http_redis = activate_app

    # Use a SEPARATE fakeredis instance for this test so it is fully isolated
    fake_redis = fakeredis_async.FakeRedis(decode_responses=True)

    customer = await _make_user(session_factory)
    _license_id, raw_key = await _make_pending_license(
        session_factory, customer_id=customer.id
    )

    key_hash_value = hash_key(raw_key)
    lock_key = f"lock:activate:{key_hash_value}"

    # Invoke through a real DB session so the lock gets acquired then the
    # exception fires at commit time
    commit_called = False

    async with session_factory() as session:
        # Patch session.commit to blow up after the lock is acquired
        real_commit = session.commit

        async def boom():
            nonlocal commit_called
            commit_called = True
            raise RuntimeError("Simulated DB failure mid-activation")

        session.commit = boom

        with pytest.raises(RuntimeError, match="Simulated DB failure"):
            await activate_license(
                session=session,
                redis=fake_redis,
                request=ActivateRequest(raw_key=raw_key),
            )

        session.commit = real_commit  # restore for session teardown

    # Lock must be gone — finally block must have released it
    lock_val = await fake_redis.get(lock_key)
    assert lock_val is None, (
        f"Lock was NOT released after exception; key still holds: {lock_val!r}"
    )
    assert commit_called, "Patched commit was never called — test setup error"

    await fake_redis.aclose()
