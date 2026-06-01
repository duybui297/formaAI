"""
TASK-4.2-a: End-to-end license lifecycle integration test.

Flow: admin creates license → user activates → assert DB row ACTIVE + Redis cache set.

Runs against a REAL PostgreSQL (localhost:5432) using the repo's .env settings.
Redis is replaced by fakeredis (NX/EX semantics are identical) — no live Redis needed.

Marked @pytest.mark.integration — run with:
    cd backend && uv run pytest -o addopts="" -m integration tests/integration/test_license_e2e.py -q
"""
from __future__ import annotations

import json
import os
import uuid
from datetime import timezone
from typing import AsyncGenerator

import fakeredis.aioredis as fakeredis_async
import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

# ---------------------------------------------------------------------------
# Helpers to build the real DB URL from env / .env
# ---------------------------------------------------------------------------

def _real_db_url() -> str:
    """Return asyncpg DSN for the real local Postgres.

    Prefers DATABASE_URL from env (set by backend/.env) converted to asyncpg.
    Falls back to a known-good default matching the task description.
    """
    raw = os.environ.get("DATABASE_URL", "")
    if raw:
        # Strip +asyncpg / +psycopg2 suffixes, then re-add asyncpg driver
        if "postgresql" in raw:
            # Normalise: strip any driver suffix then add asyncpg
            base = raw.split("://", 1)
            scheme = base[0].split("+")[0]  # "postgresql"
            rest = base[1]
            return f"{scheme}+asyncpg://{rest}"
    # Default from task description
    return "postgresql+asyncpg://postgres:postgres@localhost:5432/aitranslation"


# ---------------------------------------------------------------------------
# Per-test fixtures — function-scoped to avoid event-loop mismatch with asyncpg
# ---------------------------------------------------------------------------

@pytest_asyncio.fixture
async def pg_engine():
    """Real asyncpg engine against local Postgres."""
    url = _real_db_url()
    engine = create_async_engine(url, echo=False, pool_pre_ping=True)
    # Verify connectivity — fail fast with a clear message.
    try:
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
    except Exception as exc:
        await engine.dispose()
        pytest.skip(
            f"Real Postgres not reachable at {url!r}: {exc}. "
            "Start Postgres or check DATABASE_URL to run integration tests."
        )
    yield engine
    await engine.dispose()


@pytest_asyncio.fixture
async def pg_session_factory(pg_engine):
    return async_sessionmaker(pg_engine, expire_on_commit=False)


# ---------------------------------------------------------------------------
# Per-test fixtures
# ---------------------------------------------------------------------------

@pytest_asyncio.fixture
async def e2e_app(pg_session_factory, tmp_path):
    """
    Yield (app, session_factory, fake_redis) configured against real Postgres
    + fakeredis.  Dependency overrides for get_session / get_redis / get_settings.
    """
    from app.db.session import get_session
    from app.api.deps import get_arq_pool, get_settings, get_redis
    from app.main import app
    from unittest.mock import MagicMock

    fake_redis = fakeredis_async.FakeRedis(decode_responses=True)

    mock_arq = MagicMock()
    mock_settings = MagicMock()
    mock_settings.database_url = MagicMock(
        get_secret_value=lambda: _real_db_url().replace("+asyncpg", "")
    )
    mock_settings.redis_url = "redis://localhost:6379/0"
    mock_settings.data_dir = str(tmp_path)
    mock_settings.license_signing_secret = MagicMock(
        get_secret_value=lambda: "e2e-test-signing-secret-placeholder"
    )

    app.state.settings = mock_settings
    app.state.arq_pool = mock_arq
    app.state.redis = fake_redis
    app.state.engine = None  # not used by license routes

    async def override_get_session() -> AsyncGenerator[AsyncSession, None]:
        async with pg_session_factory() as session:
            yield session

    def override_get_arq_pool(request=None):
        return mock_arq

    def override_get_settings(request=None):
        return mock_settings

    def override_get_redis(request=None):
        return fake_redis

    app.dependency_overrides[get_session] = override_get_session
    app.dependency_overrides[get_arq_pool] = override_get_arq_pool
    app.dependency_overrides[get_settings] = override_get_settings
    app.dependency_overrides[get_redis] = override_get_redis

    yield app, pg_session_factory, fake_redis

    app.dependency_overrides.clear()
    for attr in ("settings", "arq_pool", "redis", "engine"):
        try:
            delattr(app.state, attr)
        except AttributeError:
            pass
    await fake_redis.aclose()


# ---------------------------------------------------------------------------
# Helper: insert a real User row in the live DB
# ---------------------------------------------------------------------------

async def _make_real_user(
    session_factory,
    *,
    is_superuser: bool = False,
    email: str | None = None,
) -> "User":  # noqa: F821
    from app.db.models import User
    from app.core.security import hash_password

    email = email or f"e2e-{uuid.uuid4().hex[:8]}@integration.test"
    async with session_factory() as session:
        user = User(
            id=str(uuid.uuid4()),
            email=email,
            hashed_password=hash_password("Integration1!"),
            is_active=True,
            is_superuser=is_superuser,
        )
        session.add(user)
        await session.commit()
        await session.refresh(user)
        return user


async def _delete_user(session_factory, user_id: str) -> None:
    """Best-effort cleanup — remove test rows from the live DB."""
    from app.db.models import User
    async with session_factory() as session:
        user = await session.get(User, user_id)
        if user:
            await session.delete(user)
            await session.commit()


# ---------------------------------------------------------------------------
# 4.2-a: End-to-end license activate flow
# ---------------------------------------------------------------------------

@pytest.mark.integration
@pytest.mark.asyncio
async def test_license_e2e_activate_flow(e2e_app):
    """
    End-to-end: admin creates license → activate → DB row ACTIVE → Redis cache set.

    1. Admin (is_superuser=True) POSTs /admin/licenses → 201 + raw_key.
    2. POST /licenses/activate with raw_key → 200 + status=ACTIVE.
    3. DB row has status=ACTIVE, activated_at is set.
    4. fakeredis has license:{key_hash} entry with valid JSON payload.
    """
    from app.db.models import License, LicenseStatus
    from app.licensing.keygen import hash_key
    from app.core.security import create_access_token

    app, session_factory, fake_redis = e2e_app

    # Create admin and regular (customer) users in real DB
    admin_user = await _make_real_user(session_factory, is_superuser=True)
    customer_user = await _make_real_user(session_factory, is_superuser=False)

    admin_token = create_access_token({"sub": admin_user.id})

    try:
        # ------------------------------------------------------------------
        # Step 1: Admin creates a license for customer_user
        # FE contract: tier in FE vocab, customer_id is email, nested response
        # ------------------------------------------------------------------
        create_body = {
            "tier": "professional",  # FE vocab → stored as PRO
            "customer_id": customer_user.email,  # email, resolved to UUID FK
            "max_devices": 2,
        }

        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            r_create = await client.post(
                "/admin/licenses",
                json=create_body,
                headers={"Authorization": f"Bearer {admin_token}"},
            )

        assert r_create.status_code == 201, (
            f"Expected 201 from create, got {r_create.status_code}: {r_create.text}"
        )
        create_data = r_create.json()
        # Nested response: { license: {...}, raw_key: str }
        assert "raw_key" in create_data, "raw_key must be at top level of create response"
        assert "license" in create_data, "license must be nested in create response"
        raw_key = create_data["raw_key"]
        assert raw_key is not None and len(raw_key) > 0, "raw_key must be non-empty"
        license_id = create_data["license"]["id"]

        # Verify initial DB state: PENDING
        async with session_factory() as session:
            lic = await session.get(License, license_id)
            assert lic is not None, "License row not found in DB after create"
            assert lic.status == LicenseStatus.PENDING, (
                f"Expected PENDING after create, got {lic.status}"
            )

        # ------------------------------------------------------------------
        # Step 2: Activate the license (public endpoint, no auth)
        # ------------------------------------------------------------------
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            r_activate = await client.post(
                "/licenses/activate",
                json={"raw_key": raw_key},
            )

        assert r_activate.status_code == 200, (
            f"Expected 200 from activate, got {r_activate.status_code}: {r_activate.text}"
        )
        act_data = r_activate.json()
        assert act_data["status"] == "ACTIVE", f"Expected ACTIVE, got {act_data['status']}"
        assert act_data["activated_at"] is not None, "activated_at must be set"
        assert act_data["expired_at"] is not None, "expired_at must be set (tier default)"
        assert act_data["id"] == license_id, "Response id must match created license id"

        # ------------------------------------------------------------------
        # Step 3: Assert DB row is ACTIVE
        # ------------------------------------------------------------------
        async with session_factory() as session:
            lic = await session.get(License, license_id)
            assert lic is not None
            assert lic.status == LicenseStatus.ACTIVE, (
                f"DB row still has status={lic.status} after activation"
            )
            assert lic.activated_at is not None, "DB activated_at must be set"
            assert lic.expired_at is not None, "DB expired_at must be set"

        # ------------------------------------------------------------------
        # Step 4: Assert Redis cache entry exists (fakeredis)
        # ------------------------------------------------------------------
        key_hash_value = hash_key(raw_key)
        cache_key = f"license:{key_hash_value}"
        cached_raw = await fake_redis.get(cache_key)
        assert cached_raw is not None, (
            f"Redis cache key {cache_key!r} not found after activation"
        )

        cached = json.loads(cached_raw)
        assert cached["status"] == "ACTIVE", f"Cached status: {cached['status']}"
        assert cached["id"] == license_id, "Cached id must match license id"
        assert cached["tier"] == "PRO", f"Cached tier: {cached['tier']}"

        # TTL must be positive
        ttl = await fake_redis.ttl(cache_key)
        assert ttl > 0, f"Cache key has zero/negative TTL: {ttl}"

    finally:
        # Best-effort cleanup of test rows from the live DB
        # (license is cascade-deleted when user is deleted)
        await _delete_user(session_factory, customer_user.id)
        await _delete_user(session_factory, admin_user.id)
