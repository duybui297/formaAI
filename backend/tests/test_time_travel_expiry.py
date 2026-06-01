"""Tests for TASK-4.1 — Time-travel expiry boundary testing.

Verification command (featurelist.json 4.1-b):
  cd backend && uv run pytest -o addopts="" tests/test_time_travel_expiry.py -k boundary_before_after -q

Tests the real expiry-check code path in both the cache-HIT (_cache_entry_valid)
and cache-MISS (DB fallback in LicenseValidationMiddleware) branches.

Clock is injected by monkeypatching app.api.middleware.license._utcnow — the
minimal testability hook added to the middleware.  No sleeps, no real-time
dependency.
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
from starlette.requests import Request

TEST_DB_URL = "sqlite+aiosqlite:///:memory:"

# ---------------------------------------------------------------------------
# Fixed reference time for all tests in this module
# ---------------------------------------------------------------------------
_T = datetime(2026, 7, 1, 12, 0, 0, tzinfo=timezone.utc)
_BEFORE = _T - timedelta(seconds=1)   # expired_at - 1s  → still valid
_AFTER = _T + timedelta(seconds=1)    # expired_at + 1s  → expired


# ---------------------------------------------------------------------------
# Minimal ASGI app with a /v1/ping route for middleware testing
# ---------------------------------------------------------------------------

def _make_test_app(engine, fake_redis):
    """Return a FastAPI app with LicenseValidationMiddleware attached.

    Attaches the middleware the same way main.py does.  Sets app.state.redis
    and app.state.engine so the middleware's DB-miss path can resolve.
    """
    from app.api.middleware.license import LicenseValidationMiddleware

    test_app = FastAPI()

    @test_app.get("/v1/ping")
    async def ping():
        return JSONResponse({"ok": True})

    test_app.add_middleware(LicenseValidationMiddleware)
    test_app.state.redis = fake_redis
    test_app.state.engine = engine
    return test_app


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

async def _make_active_license(
    session_factory,
    *,
    key_hash: str,
    expired_at: datetime,
) -> None:
    """Insert an ACTIVE license with the given key_hash and expired_at."""
    from app.db.models import License, LicenseStatus, LicenseTier

    async with session_factory() as session:
        lic = License(
            id=str(uuid.uuid4()),
            key_hash=key_hash,
            tier=LicenseTier.PRO,
            status=LicenseStatus.ACTIVE,
            customer_id=str(uuid.uuid4()),
            max_devices=1,
            expired_at=expired_at,
        )
        session.add(lic)
        await session.commit()


# ---------------------------------------------------------------------------
# 4.1-b: boundary_before_after
# ---------------------------------------------------------------------------


class TestBoundaryBeforeAfter:
    """Group so -k boundary_before_after matches both sub-cases in one run."""

    # ------------------------------------------------------------------
    # Cache-HIT path: test _cache_entry_valid directly
    # ------------------------------------------------------------------

    def test_boundary_before_after_cache_hit_valid(self):
        """_cache_entry_valid: expired_at = T, now = T-1s → valid (True)."""
        from app.api.middleware import license as lic_mod

        cached = {
            "status": "ACTIVE",
            "expired_at": _T.isoformat(),
        }

        with patch.object(lic_mod, "_utcnow", return_value=_BEFORE):
            result = lic_mod._cache_entry_valid(cached)

        assert result is True, (
            f"Expected valid at T-1s (now={_BEFORE.isoformat()}), "
            f"expired_at={_T.isoformat()}"
        )

    def test_boundary_before_after_cache_hit_expired(self):
        """_cache_entry_valid: expired_at = T, now = T+1s → expired (False)."""
        from app.api.middleware import license as lic_mod

        cached = {
            "status": "ACTIVE",
            "expired_at": _T.isoformat(),
        }

        with patch.object(lic_mod, "_utcnow", return_value=_AFTER):
            result = lic_mod._cache_entry_valid(cached)

        assert result is False, (
            f"Expected invalid at T+1s (now={_AFTER.isoformat()}), "
            f"expired_at={_T.isoformat()}"
        )

    # ------------------------------------------------------------------
    # Cache-MISS (DB) path: real middleware with a frozen clock
    # ------------------------------------------------------------------

    @pytest.mark.asyncio
    async def test_boundary_before_after_db_miss_valid(self, tmp_path):
        """DB-miss path: expired_at = T, now = T-1s → middleware allows (200)."""
        from app.api.middleware import license as lic_mod
        from app.db.models import Base

        engine = create_async_engine(TEST_DB_URL, echo=False)
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        session_factory = async_sessionmaker(engine, expire_on_commit=False)
        fake_redis = fakeredis_async.FakeRedis(decode_responses=True)

        raw_key = f"test-key-{uuid.uuid4().hex}"
        from app.licensing.keygen import hash_key
        kh = hash_key(raw_key)

        # Seed ACTIVE license expiring exactly at _T
        await _make_active_license(session_factory, key_hash=kh, expired_at=_T)

        app = _make_test_app(engine, fake_redis)

        try:
            # Freeze clock at T-1s (license is still valid)
            with patch.object(lic_mod, "_utcnow", return_value=_BEFORE):
                async with AsyncClient(
                    transport=ASGITransport(app=app), base_url="http://test"
                ) as c:
                    r = await c.get(
                        "/v1/ping",
                        headers={"X-License-Key": raw_key},
                    )

            assert r.status_code == 200, (
                f"Expected 200 at T-1s, got {r.status_code}: {r.text}"
            )
        finally:
            await fake_redis.aclose()
            await engine.dispose()

    @pytest.mark.asyncio
    async def test_boundary_before_after_db_miss_expired(self, tmp_path):
        """DB-miss path: expired_at = T, now = T+1s → middleware rejects (403)."""
        from app.api.middleware import license as lic_mod
        from app.db.models import Base

        engine = create_async_engine(TEST_DB_URL, echo=False)
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        session_factory = async_sessionmaker(engine, expire_on_commit=False)
        fake_redis = fakeredis_async.FakeRedis(decode_responses=True)

        raw_key = f"test-key-{uuid.uuid4().hex}"
        from app.licensing.keygen import hash_key
        kh = hash_key(raw_key)

        # Seed ACTIVE license expiring exactly at _T
        await _make_active_license(session_factory, key_hash=kh, expired_at=_T)

        app = _make_test_app(engine, fake_redis)

        try:
            # Freeze clock at T+1s (license has expired)
            with patch.object(lic_mod, "_utcnow", return_value=_AFTER):
                async with AsyncClient(
                    transport=ASGITransport(app=app), base_url="http://test"
                ) as c:
                    r = await c.get(
                        "/v1/ping",
                        headers={"X-License-Key": raw_key},
                    )

            assert r.status_code == 403, (
                f"Expected 403 at T+1s, got {r.status_code}: {r.text}"
            )
            body = r.json()
            assert body.get("error") == "LICENSE_INVALID"
        finally:
            await fake_redis.aclose()
            await engine.dispose()
