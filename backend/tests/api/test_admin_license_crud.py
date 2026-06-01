"""
Tests for TASK-2.5 Admin License CRUD APIs — aligned to FE contract (TASK-3.1).

Covers:
- 2.5-a list_filter_paginate:  GET /admin/licenses → envelope key 'licenses', key_masked, filters,
                               sort_by/sort_dir/issued_after/issued_before, 403 for non-admin
- 2.5-b detail_and_404:        GET /admin/licenses/{id} → License shape with key_masked (not masked_key),
                               tier/status in FE vocab, 404 for unknown, 403 for non-admin
- 2.5-c activities_timeline:   GET /admin/licenses/{id}/activities → bare JSON array newest-first,
                               items have action/actor/detail fields, 403 for non-admin
- 2.5-d suspend_revoke:        POST /admin/licenses/suspend and /revoke with { ids: [...] }
                               status transitions, audit rows, Redis invalidation,
                               invalid-transition rejections
- 2.5-e extend_expiry:         POST /admin/licenses/{id}/extend body { expired_at: "<ISO>" }
                               sets absolute expiry, appends EXTENDED audit row, refreshes Redis TTL
- 2.5-f fe_vocab_mapping:      all read/list endpoints emit FE-vocab tier/status + email customer_id;
                               list filters accept FE vocab and decode to BE enum correctly
"""
from __future__ import annotations

import json
import uuid
from datetime import datetime, timedelta, timezone
from typing import AsyncGenerator
from unittest.mock import AsyncMock, MagicMock

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

TEST_DB_URL = "sqlite+aiosqlite:///:memory:"


# ---------------------------------------------------------------------------
# Shared fixture
# ---------------------------------------------------------------------------

@pytest_asyncio.fixture
async def admin_app(tmp_path):
    """
    Yield (app, session_factory, mock_redis) with:
    - SQLite in-memory DB, all tables created
    - Dependency overrides for get_session, get_settings, get_redis
    - NO override for require_admin — tests build users and override explicitly
    """
    from app.db.models import Base
    from app.db.session import get_session
    from app.api.deps import get_arq_pool, get_settings, get_redis
    from app.main import app

    engine = create_async_engine(TEST_DB_URL, echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    session_factory = async_sessionmaker(engine, expire_on_commit=False)

    mock_arq = MagicMock()
    mock_redis = AsyncMock()
    mock_redis.delete = AsyncMock(return_value=1)
    mock_redis.get = AsyncMock(return_value=None)
    mock_redis.set = AsyncMock(return_value=True)

    mock_settings = MagicMock()
    mock_settings.database_url = MagicMock(get_secret_value=lambda: TEST_DB_URL)
    mock_settings.redis_url = "redis://localhost:6379/0"
    mock_settings.data_dir = str(tmp_path)
    mock_settings.license_signing_secret = MagicMock(
        get_secret_value=lambda: "test-license-signing-secret-placeholder"
    )

    app.state.settings = mock_settings
    app.state.arq_pool = mock_arq
    app.state.redis = mock_redis
    app.state.engine = engine

    async def override_get_session() -> AsyncGenerator[AsyncSession, None]:
        async with session_factory() as session:
            yield session

    def override_get_arq_pool(request=None):
        return mock_arq

    def override_get_settings(request=None):
        return mock_settings

    def override_get_redis(request=None):
        return mock_redis

    app.dependency_overrides[get_session] = override_get_session
    app.dependency_overrides[get_arq_pool] = override_get_arq_pool
    app.dependency_overrides[get_settings] = override_get_settings
    app.dependency_overrides[get_redis] = override_get_redis

    yield app, session_factory, mock_redis

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
    from app.core.security import create_access_token
    return create_access_token({"sub": user_id})


async def _create_license_via_api(client, admin_token, customer_email, fe_tier="professional"):
    """POST /admin/licenses and return the top-level JSON response dict.

    The nested FE contract shape is: { license: {...}, raw_key: str }
    This helper returns the full dict; callers use resp["license"]["id"] etc.
    """
    r = await client.post(
        "/admin/licenses",
        json={"tier": fe_tier, "customer_id": customer_email, "max_devices": 2},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert r.status_code == 201, r.text
    return r.json()


async def _make_active_license(session_factory, customer_id):
    """Insert a License row directly with status=ACTIVE and a real expired_at."""
    from app.db.models import License, LicenseActivity, LicenseEventType, LicenseStatus, LicenseTier
    from app.licensing.keygen import generate_license_key, hash_key

    raw_key = generate_license_key("test-secret", customer_id)
    kh = hash_key(raw_key)
    now = datetime.now(timezone.utc)
    expired_at = now + timedelta(days=365)

    async with session_factory() as session:
        lic = License(
            id=str(uuid.uuid4()),
            key_hash=kh,
            tier=LicenseTier.PRO,
            status=LicenseStatus.ACTIVE,
            customer_id=customer_id,
            max_devices=2,
            activated_at=now,
            expired_at=expired_at,
        )
        session.add(lic)
        await session.flush()
        session.add(LicenseActivity(
            license_id=lic.id,
            event_type=LicenseEventType.CREATED,
            actor_id=customer_id,
        ))
        await session.commit()
        await session.refresh(lic)
        return lic, raw_key


# ===========================================================================
# 2.5-a — list_filter_paginate
# ===========================================================================

@pytest.mark.asyncio
async def test_list_filter_paginate(admin_app):
    """
    GET /admin/licenses returns paginated envelope with key 'licenses' (not 'items').
    Items have key_masked (not masked_key), no raw_key, no key_hash.
    Filters by FE-vocab tier and status work.
    issued_after / issued_before / sort_by / sort_dir accepted without error.
    Non-admin caller gets 403.
    """
    app, session_factory, mock_redis = admin_app

    admin_user = await _make_user(session_factory, is_superuser=True)
    non_admin = await _make_user(session_factory, is_superuser=False)
    customer = await _make_user(session_factory, is_superuser=False)
    admin_token = _admin_token(admin_user.id)
    non_admin_token = _admin_token(non_admin.id)

    from app.api.deps import require_admin
    app.dependency_overrides[require_admin] = lambda: admin_user

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        # Create 3 licenses: 2 professional (PRO) + 1 starter (TRIAL)
        for _ in range(2):
            await _create_license_via_api(c, admin_token, customer.email, fe_tier="professional")
        await _create_license_via_api(c, admin_token, customer.email, fe_tier="starter")

        # --- baseline: list all — envelope key is 'licenses' ---
        r = await c.get(
            "/admin/licenses",
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert r.status_code == 200, r.text
        data = r.json()
        assert "licenses" in data, f"Expected 'licenses' key, got keys: {list(data.keys())}"
        assert "items" not in data, "Must not have old 'items' key"
        assert "total" in data
        assert "page" in data
        assert "page_size" in data
        assert data["total"] >= 3

        # --- each item has key_masked (not masked_key) ---
        first_item = data["licenses"][0]
        assert "key_masked" in first_item, f"Expected 'key_masked', got: {list(first_item.keys())}"
        assert "masked_key" not in first_item, "Must not have old 'masked_key' field"
        assert "raw_key" not in first_item
        assert "key_hash" not in first_item
        # key_masked format: ****-****-****-XXXX
        assert first_item["key_masked"].startswith("****-****-****-")

        # --- items use FE vocab (not BE enum) ---
        for item in data["licenses"]:
            assert item["tier"] in ("professional", "starter"), f"Unexpected tier: {item['tier']}"
            assert item["status"] in ("pending", "active", "suspended", "revoked", "expired"), \
                f"Unexpected status: {item['status']}"

        # --- filter by FE tier=professional (maps to BE PRO) ---
        r = await c.get(
            "/admin/licenses?tier=professional",
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert r.status_code == 200, r.text
        pro_data = r.json()
        assert all(item["tier"] == "professional" for item in pro_data["licenses"]), \
            f"Expected all 'professional', got: {[i['tier'] for i in pro_data['licenses']]}"

        # --- filter by FE status=pending (maps to BE PENDING) ---
        r = await c.get(
            "/admin/licenses?status=pending",
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert r.status_code == 200, r.text
        pending_data = r.json()
        assert all(item["status"] == "pending" for item in pending_data["licenses"]), \
            f"Expected all 'pending', got: {[i['status'] for i in pending_data['licenses']]}"

        # --- pagination: page_size=1 ---
        r = await c.get(
            "/admin/licenses?page=1&page_size=1",
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert r.status_code == 200, r.text
        paged = r.json()
        assert len(paged["licenses"]) == 1
        assert paged["page"] == 1
        assert paged["page_size"] == 1

        # --- sort_by / sort_dir accepted ---
        r = await c.get(
            "/admin/licenses?sort_by=issued_at&sort_dir=asc",
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert r.status_code == 200, r.text

        # --- issued_after / issued_before accepted ---
        past = (datetime.now(timezone.utc) - timedelta(days=1)).isoformat()
        future = (datetime.now(timezone.utc) + timedelta(days=1)).isoformat()
        r = await c.get(
            f"/admin/licenses?issued_after={past}&issued_before={future}",
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert r.status_code == 200, r.text
        assert r.json()["total"] >= 3

        # --- search by email substring ---
        r = await c.get(
            f"/admin/licenses?search={customer.email[:8]}",
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert r.status_code == 200, r.text

    # --- non-admin gets 403 ---
    del app.dependency_overrides[require_admin]
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        r = await c.get(
            "/admin/licenses",
            headers={"Authorization": f"Bearer {non_admin_token}"},
        )
        assert r.status_code == 403, r.text


# ===========================================================================
# 2.5-b — detail_and_404
# ===========================================================================

@pytest.mark.asyncio
async def test_detail_and_404(admin_app):
    """
    GET /admin/licenses/{id} returns License shape with key_masked.
    key_masked format: ****-****-****-XXXX.
    tier in FE vocab, status in FE lowercase.
    No key_hash, no raw_key, no created_at/updated_at (FE does not use them).
    Unknown id → 404.  Non-admin → 403.
    """
    app, session_factory, mock_redis = admin_app

    admin_user = await _make_user(session_factory, is_superuser=True)
    non_admin = await _make_user(session_factory, is_superuser=False)
    customer = await _make_user(session_factory, is_superuser=False)
    admin_token = _admin_token(admin_user.id)
    non_admin_token = _admin_token(non_admin.id)

    from app.api.deps import require_admin
    app.dependency_overrides[require_admin] = lambda: admin_user

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        created = await _create_license_via_api(c, admin_token, customer.email)
        license_id = created["license"]["id"]

        r = await c.get(
            f"/admin/licenses/{license_id}",
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert r.status_code == 200, r.text
        detail = r.json()

        # Required FE fields
        assert detail["id"] == license_id
        assert "key_masked" in detail, f"Expected 'key_masked', got: {list(detail.keys())}"
        assert "masked_key" not in detail, "Must not have old 'masked_key'"
        # key_masked format: ****-****-****-XXXX
        assert detail["key_masked"].startswith("****-****-****-"), detail["key_masked"]
        assert len(detail["key_masked"]) == len("****-****-****-XXXX")

        assert "key_hash" not in detail
        assert "raw_key" not in detail
        # FE vocab tier/status
        assert detail["tier"] == "professional", f"Expected 'professional', got {detail['tier']!r}"
        assert detail["status"] == "pending", f"Expected 'pending', got {detail['status']!r}"
        assert detail["max_devices"] == 2
        assert "issued_at" in detail
        assert "activated_at" in detail
        assert "expired_at" in detail
        assert "customer_id" in detail
        assert detail["customer_id"] == customer.email

        # --- unknown id → 404 ---
        r = await c.get(
            f"/admin/licenses/{uuid.uuid4()}",
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert r.status_code == 404, r.text

    # --- non-admin → 403 ---
    del app.dependency_overrides[require_admin]
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        r = await c.get(
            f"/admin/licenses/{license_id}",
            headers={"Authorization": f"Bearer {non_admin_token}"},
        )
        assert r.status_code == 403, r.text


# ===========================================================================
# 2.5-c — activities_timeline
# ===========================================================================

@pytest.mark.asyncio
async def test_activities_timeline(admin_app):
    """
    GET /admin/licenses/{id}/activities returns a BARE JSON array (not an envelope).
    Items have: id, license_id, action (not event_type), actor (not actor_id),
                detail (nullable), created_at.
    Ordered newest-first.  Admin-gated — non-admin gets 403.
    """
    app, session_factory, mock_redis = admin_app

    admin_user = await _make_user(session_factory, is_superuser=True)
    non_admin = await _make_user(session_factory, is_superuser=False)
    customer = await _make_user(session_factory, is_superuser=False)
    admin_token = _admin_token(admin_user.id)
    non_admin_token = _admin_token(non_admin.id)

    from app.api.deps import require_admin
    app.dependency_overrides[require_admin] = lambda: admin_user

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        created = await _create_license_via_api(c, admin_token, customer.email)
        license_id = created["license"]["id"]

        r = await c.get(
            f"/admin/licenses/{license_id}/activities",
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert r.status_code == 200, r.text
        data = r.json()

        # Must be a bare array — NOT an object with 'items'/'total'
        assert isinstance(data, list), f"Expected list, got {type(data)}: {data}"
        assert len(data) >= 1

        # Each item has FE fields
        for item in data:
            assert item["license_id"] == license_id
            assert "action" in item, f"Expected 'action', got: {list(item.keys())}"
            assert "event_type" not in item, "Must not have old 'event_type'"
            assert "actor" in item, f"Expected 'actor', got: {list(item.keys())}"
            assert "actor_id" not in item, "Must not have old 'actor_id'"
            assert "detail" in item  # nullable, but key must exist
            assert "created_at" in item
            assert "id" in item

        # Newest-first
        if len(data) > 1:
            timestamps = [item["created_at"] for item in data]
            assert timestamps == sorted(timestamps, reverse=True)

        # Unknown license → 404
        r = await c.get(
            f"/admin/licenses/{uuid.uuid4()}/activities",
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert r.status_code == 404, r.text

    # Non-admin → 403
    del app.dependency_overrides[require_admin]
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        r = await c.get(
            f"/admin/licenses/{license_id}/activities",
            headers={"Authorization": f"Bearer {non_admin_token}"},
        )
        assert r.status_code == 403, r.text


# ===========================================================================
# 2.5-d — suspend_revoke
# ===========================================================================

@pytest.mark.asyncio
async def test_suspend_revoke(admin_app):
    """
    POST /admin/licenses/suspend  body { ids: ["id1",...] }  ACTIVE → SUSPENDED
    POST /admin/licenses/revoke   body { ids: ["id1",...] }  any → REVOKED
    Audit rows appended.  Redis DEL called.
    Invalid transitions: suspend non-ACTIVE → 400; already-suspended → 409;
                         revoke already-revoked → 409.
    Non-admin → 403 for both endpoints.
    """
    app, session_factory, mock_redis = admin_app

    admin_user = await _make_user(session_factory, is_superuser=True)
    non_admin = await _make_user(session_factory, is_superuser=False)
    customer = await _make_user(session_factory, is_superuser=False)
    admin_token = _admin_token(admin_user.id)
    non_admin_token = _admin_token(non_admin.id)

    from app.api.deps import require_admin
    app.dependency_overrides[require_admin] = lambda: admin_user

    # --- suspend: ACTIVE → SUSPENDED ---
    lic, _ = await _make_active_license(session_factory, customer.id)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        r = await c.post(
            "/admin/licenses/suspend",
            json={"ids": [lic.id]},
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert r.status_code == 200, r.text

        # Redis DEL was called for the license cache key
        mock_redis.delete.assert_called()
        called_args = [str(call) for call in mock_redis.delete.call_args_list]
        assert any(lic.key_hash in a for a in called_args)

        # Audit row exists with event_type SUSPENDED
        async with session_factory() as session:
            from app.db.models import LicenseActivity
            result = await session.execute(
                select(LicenseActivity)
                .where(LicenseActivity.license_id == lic.id)
                .where(LicenseActivity.event_type == "SUSPENDED")
            )
            suspended_rows = result.scalars().all()
            assert len(suspended_rows) == 1
            assert suspended_rows[0].actor_id == admin_user.id

        # Suspending already-suspended → 409
        r = await c.post(
            "/admin/licenses/suspend",
            json={"ids": [lic.id]},
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert r.status_code == 409, r.text

    # --- revoke: PENDING → REVOKED ---
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        created = await _create_license_via_api(c, admin_token, customer.email)
        license_id_pending = created["license"]["id"]

        r = await c.post(
            "/admin/licenses/revoke",
            json={"ids": [license_id_pending]},
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert r.status_code == 200, r.text

        # Verify status changed
        async with session_factory() as session:
            from app.db.models import License
            row = await session.get(License, license_id_pending)
            assert row.status.value == "REVOKED"

        # Revoking already-revoked → 409
        r = await c.post(
            "/admin/licenses/revoke",
            json={"ids": [license_id_pending]},
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert r.status_code == 409, r.text

    # --- suspending a PENDING license is invalid (not ACTIVE) → 400 ---
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        created2 = await _create_license_via_api(c, admin_token, customer.email)
        r = await c.post(
            "/admin/licenses/suspend",
            json={"ids": [created2["license"]["id"]]},
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert r.status_code == 400, r.text

    # --- empty ids → 400 ---
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        r = await c.post(
            "/admin/licenses/suspend",
            json={"ids": []},
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert r.status_code == 400, r.text

    # --- non-admin → 403 ---
    del app.dependency_overrides[require_admin]
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        r = await c.post(
            "/admin/licenses/suspend",
            json={"ids": [lic.id]},
            headers={"Authorization": f"Bearer {non_admin_token}"},
        )
        assert r.status_code == 403, r.text

        r = await c.post(
            "/admin/licenses/revoke",
            json={"ids": [lic.id]},
            headers={"Authorization": f"Bearer {non_admin_token}"},
        )
        assert r.status_code == 403, r.text


# ===========================================================================
# 2.5-e — extend_expiry
# ===========================================================================

@pytest.mark.asyncio
async def test_extend_expiry(admin_app):
    """
    POST /admin/licenses/{id}/extend  body { expired_at: "<ISO>" }
    Sets expired_at to the given absolute datetime (must be in the future).
    Appends EXTENDED audit row.
    Refreshes Redis TTL when license is ACTIVE and cache entry exists.
    Past expired_at → 400.
    Extending a REVOKED license → 400.
    """
    app, session_factory, mock_redis = admin_app

    admin_user = await _make_user(session_factory, is_superuser=True)
    customer = await _make_user(session_factory, is_superuser=False)
    admin_token = _admin_token(admin_user.id)

    from app.api.deps import require_admin
    app.dependency_overrides[require_admin] = lambda: admin_user

    lic, _ = await _make_active_license(session_factory, customer.id)

    # Simulate an existing Redis cache entry
    async with session_factory() as session:
        from app.db.models import License
        row = await session.get(License, lic.id)
        original_expired_at = row.expired_at
        if original_expired_at.tzinfo is None:
            original_expired_at = original_expired_at.replace(tzinfo=timezone.utc)

    cache_payload = json.dumps({
        "id": lic.id,
        "tier": "PRO",
        "status": "ACTIVE",
        "activated_at": datetime.now(timezone.utc).isoformat(),
        "expired_at": original_expired_at.isoformat(),
    })
    mock_redis.get = AsyncMock(return_value=cache_payload)

    # Set an absolute expiry 60 days from now
    new_expiry = datetime.now(timezone.utc) + timedelta(days=60)
    new_expiry_iso = new_expiry.isoformat()

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        r = await c.post(
            f"/admin/licenses/{lic.id}/extend",
            json={"expired_at": new_expiry_iso},
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert r.status_code == 200, r.text
        data = r.json()
        assert data["id"] == lic.id

        # Response has key_masked (FE License shape)
        assert "key_masked" in data
        assert "masked_key" not in data

        # FE vocab
        assert data["tier"] == "professional", f"Expected 'professional', got {data['tier']!r}"
        assert data["status"] == "active", f"Expected 'active', got {data['status']!r}"

        # expired_at matches what we sent (within 2 seconds)
        returned_exp = datetime.fromisoformat(data["expired_at"].replace("Z", "+00:00"))
        if returned_exp.tzinfo is None:
            returned_exp = returned_exp.replace(tzinfo=timezone.utc)
        assert abs((returned_exp - new_expiry).total_seconds()) < 2

    # Audit row EXTENDED exists
    async with session_factory() as session:
        from app.db.models import LicenseActivity
        result = await session.execute(
            select(LicenseActivity)
            .where(LicenseActivity.license_id == lic.id)
            .where(LicenseActivity.event_type == "EXTENDED")
        )
        extended_rows = result.scalars().all()
        assert len(extended_rows) == 1
        assert extended_rows[0].actor_id == admin_user.id
        meta = extended_rows[0].event_metadata
        assert "new_expired_at" in meta

    # Redis set was called (TTL refresh)
    mock_redis.set.assert_called()

    # --- past expired_at → 400 ---
    past_iso = (datetime.now(timezone.utc) - timedelta(days=1)).isoformat()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        r = await c.post(
            f"/admin/licenses/{lic.id}/extend",
            json={"expired_at": past_iso},
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert r.status_code in (400, 422), r.text

    # --- cannot extend a REVOKED license → 400 ---
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        created = await _create_license_via_api(c, admin_token, customer.email)
        revoke_r = await c.post(
            "/admin/licenses/revoke",
            json={"ids": [created["license"]["id"]]},
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert revoke_r.status_code == 200
        extend_r = await c.post(
            f"/admin/licenses/{created['license']['id']}/extend",
            json={"expired_at": new_expiry_iso},
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert extend_r.status_code == 400, extend_r.text

    del app.dependency_overrides[require_admin]


# ===========================================================================
# 2.5-f — fe_vocab_mapping
# ===========================================================================

@pytest.mark.asyncio
async def test_fe_vocab_mapping(admin_app):
    """FE vocab contract for all read endpoints + list filters (TASK-2.5-f).

    Verifies:
    - list items carry FE-vocab tier (starter/professional/enterprise) + lowercase status
    - list items carry EMAIL as customer_id (not UUID)
    - ?tier=professional filters correctly (maps to BE PRO)
    - ?status=suspended filters correctly (maps to BE SUSPENDED)
    - GET detail uses FE vocab
    - GET activities uses FE vocab for action (lowercase event type is fine)
    - PENDING license appears with status="pending"
    """
    app, session_factory, mock_redis = admin_app

    admin_user = await _make_user(session_factory, is_superuser=True)
    admin_token = _admin_token(admin_user.id)

    # Create customers with predictable emails
    starter_cust = await _make_user(
        session_factory, email="starter@vocab-test.com", is_superuser=False
    )
    pro_cust = await _make_user(
        session_factory, email="pro@vocab-test.com", is_superuser=False
    )
    ent_cust = await _make_user(
        session_factory, email="ent@vocab-test.com", is_superuser=False
    )

    from app.api.deps import require_admin
    app.dependency_overrides[require_admin] = lambda: admin_user

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        # --- seed licenses across tiers (all PENDING initially) ---
        starter_resp = await _create_license_via_api(c, admin_token, starter_cust.email, fe_tier="starter")
        pro_resp = await _create_license_via_api(c, admin_token, pro_cust.email, fe_tier="professional")
        ent_resp = await _create_license_via_api(c, admin_token, ent_cust.email, fe_tier="enterprise")

        starter_id = starter_resp["license"]["id"]
        pro_id = pro_resp["license"]["id"]
        ent_id = ent_resp["license"]["id"]

        # --- make one license ACTIVE + SUSPENDED directly in DB ---
        # Insert an ACTIVE PRO license
        lic_active, _ = await _make_active_license(session_factory, pro_cust.id)

        # Suspend that license via API
        r = await c.post(
            "/admin/licenses/suspend",
            json={"ids": [lic_active.id]},
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert r.status_code == 200, r.text

        # ---- list all → verify FE vocab + email ----
        r = await c.get(
            "/admin/licenses",
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert r.status_code == 200, r.text
        all_data = r.json()
        assert "licenses" in all_data

        # Build id → item map
        items_by_id = {item["id"]: item for item in all_data["licenses"]}

        # Starter license
        s = items_by_id.get(starter_id)
        assert s is not None, "starter license missing from list"
        assert s["tier"] == "starter", f"Expected 'starter', got {s['tier']!r}"
        assert s["status"] == "pending"
        assert s["customer_id"] == starter_cust.email, \
            f"Expected email, got {s['customer_id']!r}"

        # Pro PENDING license
        p = items_by_id.get(pro_id)
        assert p is not None, "pro license missing from list"
        assert p["tier"] == "professional"
        assert p["status"] == "pending"
        assert p["customer_id"] == pro_cust.email

        # Enterprise license
        e = items_by_id.get(ent_id)
        assert e is not None, "enterprise license missing from list"
        assert e["tier"] == "enterprise"
        assert e["status"] == "pending"
        assert e["customer_id"] == ent_cust.email

        # Suspended license
        susp = items_by_id.get(lic_active.id)
        assert susp is not None, "suspended license missing from list"
        assert susp["tier"] == "professional"  # PRO → professional
        assert susp["status"] == "suspended"   # SUSPENDED → suspended

        # ---- ?tier=professional filter ----
        r = await c.get(
            "/admin/licenses?tier=professional",
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert r.status_code == 200, r.text
        filtered = r.json()
        pro_items = filtered["licenses"]
        assert len(pro_items) >= 1
        assert all(item["tier"] == "professional" for item in pro_items), \
            f"Non-professional items slipped through: {[(i['id'], i['tier']) for i in pro_items]}"

        # ---- ?status=suspended filter ----
        r = await c.get(
            "/admin/licenses?status=suspended",
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert r.status_code == 200, r.text
        suspended_items = r.json()["licenses"]
        assert len(suspended_items) >= 1
        assert all(item["status"] == "suspended" for item in suspended_items), \
            f"Non-suspended items: {[(i['id'], i['status']) for i in suspended_items]}"
        # customer_id is email in filtered results too
        for item in suspended_items:
            assert "@" in (item["customer_id"] or ""), \
                f"customer_id should be email, got: {item['customer_id']!r}"

        # ---- GET detail uses FE vocab ----
        r = await c.get(
            f"/admin/licenses/{starter_id}",
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert r.status_code == 200, r.text
        detail = r.json()
        assert detail["tier"] == "starter"
        assert detail["status"] == "pending"
        assert detail["customer_id"] == starter_cust.email

        # ---- GET activities — action is event type string (lowercase or UPPER, just consistent) ----
        r = await c.get(
            f"/admin/licenses/{starter_id}/activities",
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert r.status_code == 200, r.text
        acts = r.json()
        assert isinstance(acts, list)
        assert len(acts) >= 1
        # action field must exist (mapped from event_type)
        for act in acts:
            assert "action" in act
            assert "event_type" not in act

    del app.dependency_overrides[require_admin]
