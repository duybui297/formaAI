"""
Tests for POST /licenses/checkout — TASK-3.3.

Covers:
- self_serve_creates_pending: authenticated (non-admin) user → 201 PENDING license
  with customer_id == user.id and raw_key returned once; unauthenticated → 401.
- plan_tier_mapping: free→TRIAL, pro→PRO, business→ENTERPRISE with correct
  max_devices; unknown plan → 422.
"""
from __future__ import annotations

import uuid
from typing import AsyncGenerator
from unittest.mock import MagicMock

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.db.models import LicenseTier

TEST_DB_URL = "sqlite+aiosqlite:///:memory:"

# ---------------------------------------------------------------------------
# Fixture: isolated app + SQLite DB (same pattern as test_admin_licenses.py)
# ---------------------------------------------------------------------------


@pytest_asyncio.fixture
async def checkout_app(tmp_path):
    """
    Yield (app, session_factory) with:
    - SQLite in-memory DB, all tables created
    - Dependency overrides for get_session, get_settings
    - Real get_current_active_user (JWT-based) — tests supply tokens
    """
    from app.db.models import Base
    from app.db.session import get_session
    from app.api.deps import get_arq_pool, get_settings
    from app.main import app

    engine = create_async_engine(TEST_DB_URL, echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    session_factory = async_sessionmaker(engine, expire_on_commit=False)

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
    app.state.redis = MagicMock()
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


async def _make_user(
    session_factory,
    *,
    is_superuser: bool = False,
    email: str | None = None,
):
    """Insert a User row and return it (committed)."""
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
    """Generate a valid JWT access token for the given user_id."""
    from app.core.security import create_access_token
    return create_access_token({"sub": user_id})


# ===========================================================================
# 3.3-a: self_serve_creates_pending
# ===========================================================================


@pytest.mark.asyncio
async def test_self_serve_creates_pending(checkout_app):
    """
    POST /licenses/checkout by an authenticated non-admin user:
    - Returns 201
    - Response has raw_key (non-empty, XXXX-XXXX-XXXX-XXXX format)
    - DB has a License row with status=PENDING, customer_id == user.id
    - DB has a LicenseActivity CREATED row
    - An unauthenticated request returns 401
    """
    app, session_factory = checkout_app

    # Create a regular (non-admin) user
    user = await _make_user(session_factory, is_superuser=False)
    token = _token(user.id)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        # --- Unauthenticated → 401 ---
        r_unauth = await c.post("/licenses/checkout", json={"plan": "pro"})
        assert r_unauth.status_code == 401, r_unauth.text

        # --- Authenticated non-admin → 201 ---
        r = await c.post(
            "/licenses/checkout",
            json={"plan": "pro"},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert r.status_code == 201, r.text
        data = r.json()

    # raw_key present and formatted
    assert data["raw_key"] is not None
    assert len(data["raw_key"]) == 19  # XXXX-XXXX-XXXX-XXXX
    assert data["raw_key"].count("-") == 3

    # Status must be PENDING
    assert data["status"] == "PENDING"

    # customer_id must equal the requesting user's id
    assert data["customer_id"] == user.id

    license_id = data["id"]

    # Verify DB state
    async with session_factory() as session:
        from app.db.models import License, LicenseActivity, LicenseStatus
        from app.licensing.keygen import hash_key

        lic = await session.get(License, license_id)
        assert lic is not None
        assert lic.status == LicenseStatus.PENDING
        assert lic.customer_id == user.id

        # raw_key not stored — only its hash
        assert lic.key_hash == hash_key(data["raw_key"])

        # LicenseActivity CREATED row
        result = await session.execute(
            select(LicenseActivity).where(LicenseActivity.license_id == license_id)
        )
        activities = result.scalars().all()
        assert len(activities) == 1
        assert activities[0].event_type.value == "CREATED"
        assert activities[0].actor_id == user.id


# ===========================================================================
# 3.3-b: plan_tier_mapping
# ===========================================================================


@pytest.mark.asyncio
async def test_plan_tier_mapping(checkout_app):
    """
    Plan → tier + max_devices mapping:
      free     → TRIAL,      max_devices=1
      pro      → PRO,        max_devices=3
      business → ENTERPRISE, max_devices=10
    Unknown plan → 422.
    """
    app, session_factory = checkout_app

    user = await _make_user(session_factory, is_superuser=False)
    token = _token(user.id)

    expected = [
        ("free",     LicenseTier.TRIAL,      1),
        ("pro",      LicenseTier.PRO,        3),
        ("business", LicenseTier.ENTERPRISE, 10),
    ]

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        for plan, expected_tier, expected_max_devices in expected:
            r = await c.post(
                "/licenses/checkout",
                json={"plan": plan},
                headers={"Authorization": f"Bearer {token}"},
            )
            assert r.status_code == 201, f"plan={plan}: {r.text}"
            data = r.json()
            assert data["tier"] == expected_tier.value, (
                f"plan={plan}: expected tier {expected_tier.value}, got {data['tier']}"
            )
            assert data["max_devices"] == expected_max_devices, (
                f"plan={plan}: expected max_devices {expected_max_devices}, got {data['max_devices']}"
            )

        # Unknown plan → 422
        r_bad = await c.post(
            "/licenses/checkout",
            json={"plan": "unknown_plan"},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert r_bad.status_code == 422, f"Expected 422 for unknown plan, got {r_bad.status_code}: {r_bad.text}"
