"""
Tests for POST /leads — TASK-3.5-b.

Covers behavior creates_lead:
  - Valid {email, plan} → 201 + row persisted in DB
  - Invalid email → 422
  - No auth required (open endpoint)

Verification command (featurelist.json):
  3.5-b: pytest tests/api/test_leads.py -k creates_lead -q
"""
from __future__ import annotations

from typing import AsyncGenerator
from unittest.mock import MagicMock

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

TEST_DB_URL = "sqlite+aiosqlite:///:memory:"


# ---------------------------------------------------------------------------
# Fixture: isolated app + SQLite DB (mirrors test_checkout.py / test_activate.py)
# ---------------------------------------------------------------------------

@pytest_asyncio.fixture
async def leads_app(tmp_path):
    """
    Yield (app, session_factory) with:
    - SQLite in-memory DB, all tables created
    - Dependency overrides for get_session, get_settings
    - No auth override — leads endpoint is open
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
# 3.5-b: creates_lead
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_creates_lead(leads_app):
    """
    POST /leads with valid {email, plan}:
    - Returns 201 with the created lead (id, email, plan, created_at)
    - Row is persisted in DB
    - No auth required (open endpoint)
    """
    app, session_factory = leads_app

    payload = {"email": "visitor@example.com", "plan": "pro"}

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        # No auth header — must succeed
        r = await c.post("/leads", json=payload)
        assert r.status_code == 201, r.text
        data = r.json()

    # Response shape
    assert data["email"] == "visitor@example.com"
    assert data["plan"] == "pro"
    assert "id" in data
    assert "created_at" in data

    # Row persisted
    from app.db.models import Lead

    async with session_factory() as session:
        result = await session.execute(
            select(Lead).where(Lead.id == data["id"])
        )
        row = result.scalar_one_or_none()
        assert row is not None, "Lead row not found in DB"
        assert row.email == "visitor@example.com"
        assert row.plan == "pro"


@pytest.mark.asyncio
async def test_creates_lead_invalid_email(leads_app):
    """POST /leads with an invalid email returns 422."""
    app, _ = leads_app

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        r = await c.post("/leads", json={"email": "not-an-email", "plan": "pro"})
        assert r.status_code == 422, r.text


@pytest.mark.asyncio
async def test_creates_lead_free_plan(leads_app):
    """POST /leads accepts plan='free' (free string, no constraint)."""
    app, session_factory = leads_app

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        r = await c.post("/leads", json={"email": "free@example.com", "plan": "free"})
        assert r.status_code == 201, r.text
        data = r.json()
        assert data["plan"] == "free"


@pytest.mark.asyncio
async def test_creates_lead_no_auth_required(leads_app):
    """POST /leads succeeds without any Authorization header."""
    app, _ = leads_app

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        # Explicitly no Authorization header
        r = await c.post(
            "/leads",
            json={"email": "anon@example.com", "plan": "business"},
        )
        assert r.status_code == 201, (
            f"Expected 201 without auth, got {r.status_code}: {r.text}"
        )
