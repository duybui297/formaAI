"""
Tests for POST /admin/licenses — TASK-2.1.

Covers:
- 2.1-a invalid_body:            422 on bad request bodies (FE vocab tier, email customer_id)
- 2.1-b rbac_and_one_time_key:   401/403 for unauth/non-admin; 201 for admin;
                                  nested { license, raw_key } with raw_key exactly once
- 2.1-c persists_pending_and_audit: DB state after create (License row + LicenseActivity CREATED row)
- 2.1-d idempotent_create:        repeat POST with same Idempotency-Key returns same license;
                                  raw_key None on replay; no dup rows
- 2.1-e create_fe_contract:       full FE contract shape — tier/status in FE vocab,
                                  customer_id is email, response nested, unknown email → 400
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

TEST_DB_URL = "sqlite+aiosqlite:///:memory:"

# ---------------------------------------------------------------------------
# Fixture: isolated app + SQLite DB + no real Redis/arq
# ---------------------------------------------------------------------------

@pytest_asyncio.fixture
async def admin_app(tmp_path):
    """
    Yield (app, session_factory) with:
    - SQLite in-memory DB, all tables created
    - Dependency overrides for get_session, get_settings
    - NO override for require_admin — tests that need admin build their own user
      and override require_admin explicitly.
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


async def _make_user(
    session_factory,
    *,
    is_superuser: bool = False,
    email: str | None = None,
) -> "User":  # noqa: F821
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


def _admin_token(user_id: str) -> str:
    """Generate a valid JWT access token for the given user_id."""
    from app.core.security import create_access_token
    return create_access_token({"sub": user_id})


# ---------------------------------------------------------------------------
# Minimal valid body (FE vocab: tier=professional, customer_id=email)
# ---------------------------------------------------------------------------

def _valid_body(customer_email: str | None = None) -> dict:
    return {
        "tier": "professional",
        "customer_id": customer_email or f"user-{uuid.uuid4().hex[:8]}@test.com",
        "max_devices": 3,
    }


# ===========================================================================
# Test: 2.1-a invalid_body
# ===========================================================================

@pytest.mark.asyncio
async def test_invalid_body(admin_app):
    """422 on missing/invalid fields (FE vocab)."""
    app, session_factory = admin_app

    admin_user = await _make_user(session_factory, is_superuser=True)

    from app.api.deps import require_admin
    app.dependency_overrides[require_admin] = lambda: admin_user

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        # Missing tier
        r = await c.post(
            "/admin/licenses",
            json={"customer_id": "some@email.com", "max_devices": 1},
        )
        assert r.status_code == 422, r.text

        # max_devices = 0 (must be > 0)
        r = await c.post(
            "/admin/licenses",
            json={"tier": "professional", "customer_id": "some@email.com", "max_devices": 0},
        )
        assert r.status_code == 422, r.text

        # invalid tier value (not in FE vocab)
        r = await c.post(
            "/admin/licenses",
            json={"tier": "INVALID", "customer_id": "some@email.com", "max_devices": 1},
        )
        assert r.status_code == 422, r.text

        # customer_id is not an email (no @)
        r = await c.post(
            "/admin/licenses",
            json={"tier": "professional", "customer_id": "not-an-email", "max_devices": 1},
        )
        assert r.status_code == 422, r.text

    del app.dependency_overrides[require_admin]


# ===========================================================================
# Test: 2.1-b rbac_and_one_time_key
# ===========================================================================

@pytest.mark.asyncio
async def test_rbac_and_one_time_key(admin_app):
    """
    - 401 when no token supplied
    - 403 when authenticated as non-admin (is_superuser=False)
    - 201 when authenticated as admin (is_superuser=True); nested response with raw_key present
    - raw_key is a non-empty string in XXXX-XXXX-XXXX-XXXX format
    - response body is nested: body["license"] exists, body["raw_key"] exists
    """
    app, session_factory = admin_app

    regular_user = await _make_user(session_factory, is_superuser=False)
    admin_user = await _make_user(session_factory, is_superuser=True)
    customer = await _make_user(session_factory, is_superuser=False)

    regular_token = _admin_token(regular_user.id)
    admin_token = _admin_token(admin_user.id)
    body = _valid_body(customer_email=customer.email)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        # 1. No token → 401
        r = await c.post("/admin/licenses", json=body)
        assert r.status_code == 401, r.text

        # 2. Non-admin token → 403
        r = await c.post(
            "/admin/licenses",
            json=body,
            headers={"Authorization": f"Bearer {regular_token}"},
        )
        assert r.status_code == 403, r.text

        # 3. Admin token → 201 with nested response + raw_key
        r = await c.post(
            "/admin/licenses",
            json=body,
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert r.status_code == 201, r.text
        data = r.json()
        # Nested shape
        assert "license" in data, f"Expected nested 'license' key, got: {list(data.keys())}"
        assert "raw_key" in data, f"Expected 'raw_key' at top level, got: {list(data.keys())}"
        assert data["raw_key"] is not None
        # format: XXXX-XXXX-XXXX-XXXX (19 chars: 16 alphanum + 3 hyphens)
        assert len(data["raw_key"]) == 19
        assert data["raw_key"].count("-") == 3
        # License shape
        lic = data["license"]
        assert lic["status"] == "pending"           # FE lowercase
        assert lic["tier"] == "professional"        # FE vocab
        assert lic["customer_id"] == customer.email # email, not UUID


# ===========================================================================
# Test: 2.1-c persists_pending_and_audit
# ===========================================================================

@pytest.mark.asyncio
async def test_persists_pending_and_audit(admin_app):
    """
    After a successful POST:
    - licenses table has one row with status=PENDING (BE enum in DB)
    - license_activities table has one row with event_type=CREATED
    - key_hash is 64-char hex (SHA-256)
    - raw_key is NOT in the DB (only key_hash persisted)
    - response body is nested { license, raw_key }
    """
    app, session_factory = admin_app

    admin_user = await _make_user(session_factory, is_superuser=True)
    admin_token = _admin_token(admin_user.id)
    customer = await _make_user(session_factory, is_superuser=False)
    body = _valid_body(customer_email=customer.email)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        r = await c.post(
            "/admin/licenses",
            json=body,
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert r.status_code == 201, r.text
        data = r.json()
        # Nested shape
        assert "license" in data
        assert "raw_key" in data
        license_id = data["license"]["id"]
        returned_raw_key = data["raw_key"]

    # Verify DB state using a fresh session
    async with session_factory() as session:
        from app.db.models import License, LicenseActivity, LicenseStatus
        from app.licensing.keygen import hash_key

        lic = await session.get(License, license_id)
        assert lic is not None
        assert lic.status == LicenseStatus.PENDING
        assert lic.max_devices == 3
        assert lic.customer_id == customer.id  # stored UUID in DB

        # key_hash is SHA-256 of raw_key
        assert lic.key_hash == hash_key(returned_raw_key)

        # raw_key is NOT stored anywhere in the DB
        assert lic.idempotency_key is None  # no idempotency key was sent

        # Audit row
        result = await session.execute(
            select(LicenseActivity).where(LicenseActivity.license_id == license_id)
        )
        activities = result.scalars().all()
        assert len(activities) == 1
        assert activities[0].event_type.value == "CREATED"
        assert activities[0].actor_id == admin_user.id


# ===========================================================================
# Test: 2.1-d idempotent_create
# ===========================================================================

@pytest.mark.asyncio
async def test_idempotent_create(admin_app):
    """
    Repeat POST with same Idempotency-Key:
    - Both calls return 201
    - Second response body["raw_key"] is None (key was only returned at initial creation)
    - Only ONE License row exists in DB
    - Only ONE LicenseActivity row exists in DB
    """
    app, session_factory = admin_app

    admin_user = await _make_user(session_factory, is_superuser=True)
    admin_token = _admin_token(admin_user.id)
    customer = await _make_user(session_factory, is_superuser=False)
    body = _valid_body(customer_email=customer.email)
    idem_key = f"idem-{uuid.uuid4().hex}"

    headers = {
        "Authorization": f"Bearer {admin_token}",
        "Idempotency-Key": idem_key,
    }

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        # First call — creates the license
        r1 = await c.post("/admin/licenses", json=body, headers=headers)
        assert r1.status_code == 201, r1.text
        d1 = r1.json()
        assert d1["raw_key"] is not None  # returned exactly once
        license_id = d1["license"]["id"]

        # Second call with same key — idempotent replay
        r2 = await c.post("/admin/licenses", json=body, headers=headers)
        assert r2.status_code == 201, r2.text
        d2 = r2.json()
        assert d2["license"]["id"] == license_id  # same license
        assert d2["raw_key"] is None  # raw_key not returned on replay

    # Only one License row
    async with session_factory() as session:
        from app.db.models import License, LicenseActivity
        result = await session.execute(
            select(License).where(License.idempotency_key == idem_key)
        )
        rows = result.scalars().all()
        assert len(rows) == 1

        # Only one audit row
        result = await session.execute(
            select(LicenseActivity).where(LicenseActivity.license_id == license_id)
        )
        activities = result.scalars().all()
        assert len(activities) == 1


# ===========================================================================
# Test: 2.1-e create_fe_contract
# ===========================================================================

@pytest.mark.asyncio
async def test_create_fe_contract(admin_app):
    """Full FE contract for POST /admin/licenses (TASK-2.1-e).

    Verifies:
    - tier in FE vocab (starter/professional/enterprise) maps correctly to stored BE enum
    - customer_id must be an EMAIL; resolved to user UUID FK in DB
    - unknown email → 400
    - response is nested: { license: <FE License shape>, raw_key: str }
    - License shape has FE-vocab tier/status and email customer_id
    - expired_at accepted as optional ISO date string
    - max_devices defaults to 1 when omitted
    """
    app, session_factory = admin_app

    admin_user = await _make_user(session_factory, is_superuser=True)
    admin_token = _admin_token(admin_user.id)

    from app.api.deps import require_admin
    app.dependency_overrides[require_admin] = lambda: admin_user

    # Create customers with known emails
    starter_customer = await _make_user(
        session_factory, email="starter_customer@example.com", is_superuser=False
    )
    pro_customer = await _make_user(
        session_factory, email="pro_customer@example.com", is_superuser=False
    )
    ent_customer = await _make_user(
        session_factory, email="ent_customer@example.com", is_superuser=False
    )

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:

        # --- A) tier=starter → stored as TRIAL, response tier="starter" ---
        r = await c.post(
            "/admin/licenses",
            json={"tier": "starter", "customer_id": starter_customer.email},
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert r.status_code == 201, r.text
        d = r.json()
        assert "license" in d, f"Response must be nested, got keys: {list(d.keys())}"
        assert "raw_key" in d
        assert d["raw_key"] is not None
        lic = d["license"]
        assert lic["tier"] == "starter", f"Expected 'starter', got {lic['tier']!r}"
        assert lic["status"] == "pending", f"Expected 'pending', got {lic['status']!r}"
        assert lic["customer_id"] == starter_customer.email
        assert lic["max_devices"] == 1  # default when omitted
        assert "key_masked" in lic
        assert lic["key_masked"].startswith("****-****-****-")
        # Verify BE stored TRIAL
        async with session_factory() as session:
            from app.db.models import License, LicenseTier
            row = await session.get(License, lic["id"])
            assert row is not None
            assert row.tier == LicenseTier.TRIAL
            assert row.customer_id == starter_customer.id  # UUID stored in DB

        # --- B) tier=professional → stored as PRO, response tier="professional" ---
        r = await c.post(
            "/admin/licenses",
            json={"tier": "professional", "customer_id": pro_customer.email, "max_devices": 5},
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert r.status_code == 201, r.text
        d = r.json()
        lic = d["license"]
        assert lic["tier"] == "professional"
        assert lic["max_devices"] == 5
        async with session_factory() as session:
            from app.db.models import License, LicenseTier
            row = await session.get(License, lic["id"])
            assert row.tier == LicenseTier.PRO

        # --- C) tier=enterprise → stored as ENTERPRISE, response tier="enterprise" ---
        r = await c.post(
            "/admin/licenses",
            json={"tier": "enterprise", "customer_id": ent_customer.email},
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert r.status_code == 201, r.text
        d = r.json()
        lic = d["license"]
        assert lic["tier"] == "enterprise"
        async with session_factory() as session:
            from app.db.models import License, LicenseTier
            row = await session.get(License, lic["id"])
            assert row.tier == LicenseTier.ENTERPRISE

        # --- D) unknown email → 400 ---
        r = await c.post(
            "/admin/licenses",
            json={"tier": "professional", "customer_id": "ghost@nobody.com"},
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert r.status_code == 400, r.text

        # --- E) customer_id not an email (no @) → 422 (schema validation) ---
        r = await c.post(
            "/admin/licenses",
            json={"tier": "professional", "customer_id": "not-an-email"},
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert r.status_code == 422, r.text

        # --- F) expired_at optional ISO string accepted ---
        r = await c.post(
            "/admin/licenses",
            json={
                "tier": "professional",
                "customer_id": pro_customer.email,
                "expired_at": "2027-12-31T23:59:59Z",
            },
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert r.status_code == 201, r.text
        d = r.json()
        assert d["license"]["expired_at"] is not None

    del app.dependency_overrides[require_admin]
