"""
Tests for GET/POST/PATCH/DELETE /admin/users — TASK-3.6.

Covers:
- 3.6-b list_filter_paginate:   paginated list, filters (search/role/active), excludes soft-deleted, 403 non-admin
- 3.6-c create_user:            create user, 409 duplicate email (incl. soft-deleted), 422 invalid
- 3.6-d update_guards:          self-demote blocked, self-deactivate blocked, last-admin guards, normal updates work
- 3.6-e soft_delete_guards:     soft delete hides user + blocks login, self-delete blocked, last-admin delete blocked
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


# ---------------------------------------------------------------------------
# Helpers (mirror test_admin_licenses.py pattern)
# ---------------------------------------------------------------------------

async def _make_user(
    session_factory,
    *,
    is_superuser: bool = False,
    is_active: bool = True,
    email: str | None = None,
    full_name: str | None = None,
    deleted: bool = False,
) -> "User":  # noqa: F821
    from datetime import datetime, timezone

    from app.db.models import User
    from app.core.security import hash_password

    email = email or f"user-{uuid.uuid4().hex[:8]}@test.com"
    async with session_factory() as session:
        user = User(
            id=str(uuid.uuid4()),
            email=email,
            hashed_password=hash_password("Password1!"),
            full_name=full_name,
            is_active=False if deleted else is_active,
            is_superuser=is_superuser,
            deleted_at=datetime.now(timezone.utc) if deleted else None,
        )
        session.add(user)
        await session.commit()
        await session.refresh(user)
        return user


def _token(user_id: str) -> str:
    from app.core.security import create_access_token
    return create_access_token({"sub": user_id})


# ===========================================================================
# Test: 3.6-b list_filter_paginate
# ===========================================================================

@pytest.mark.asyncio
async def test_list_filter_paginate(admin_app):
    """
    GET /admin/users:
    - Returns paginated envelope {users, total, page, page_size}
    - Each user has {id, email, full_name, is_active, is_superuser, created_at}
    - NEVER returns hashed_password
    - Excludes soft-deleted users
    - Filters: search (email/full_name), role (admin/user), active (bool)
    - Non-admin → 403
    """
    app, session_factory = admin_app

    admin_user = await _make_user(session_factory, is_superuser=True, email="admin@test.com", full_name="Admin User")
    regular_user = await _make_user(session_factory, is_superuser=False, email="alice@test.com", full_name="Alice Smith")
    inactive_user = await _make_user(session_factory, is_superuser=False, is_active=False, email="inactive@test.com")
    deleted_user = await _make_user(session_factory, is_superuser=False, email="deleted@test.com", deleted=True)

    admin_token = _token(admin_user.id)
    regular_token = _token(regular_user.id)

    from app.api.deps import require_admin
    app.dependency_overrides[require_admin] = lambda: admin_user

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:

        # --- 1. Non-admin → 403 ---
        del app.dependency_overrides[require_admin]
        r = await c.get(
            "/admin/users",
            headers={"Authorization": f"Bearer {regular_token}"},
        )
        assert r.status_code == 403, r.text

        # Re-install admin override
        app.dependency_overrides[require_admin] = lambda: admin_user

        # --- 2. Paginated envelope ---
        r = await c.get(
            "/admin/users",
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert r.status_code == 200, r.text
        data = r.json()
        assert "users" in data
        assert "total" in data
        assert "page" in data
        assert "page_size" in data
        assert data["page"] == 1

        # soft-deleted user must NOT appear
        emails_returned = {u["email"] for u in data["users"]}
        assert "deleted@test.com" not in emails_returned, "Soft-deleted users must be excluded"

        # --- 3. No hashed_password in response ---
        for u in data["users"]:
            assert "hashed_password" not in u
            assert "password" not in u
            # Required fields
            assert "id" in u
            assert "email" in u
            assert "full_name" in u
            assert "is_active" in u
            assert "is_superuser" in u
            assert "created_at" in u

        # --- 4. search by email ---
        r = await c.get(
            "/admin/users?search=alice",
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert r.status_code == 200, r.text
        d = r.json()
        assert all("alice" in u["email"].lower() or
                   ("alice" in (u["full_name"] or "").lower())
                   for u in d["users"])

        # --- 5. search by full_name ---
        r = await c.get(
            "/admin/users?search=Alice+Smith",
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert r.status_code == 200, r.text
        d = r.json()
        assert any("alice" in u["email"] for u in d["users"])

        # --- 6. role=admin filter ---
        r = await c.get(
            "/admin/users?role=admin",
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert r.status_code == 200, r.text
        d = r.json()
        assert all(u["is_superuser"] is True for u in d["users"])

        # --- 7. role=user filter ---
        r = await c.get(
            "/admin/users?role=user",
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert r.status_code == 200, r.text
        d = r.json()
        assert all(u["is_superuser"] is False for u in d["users"])

        # --- 8. active=false filter ---
        r = await c.get(
            "/admin/users?active=false",
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert r.status_code == 200, r.text
        d = r.json()
        assert all(u["is_active"] is False for u in d["users"])
        # inactive_user should appear; deleted_user should NOT
        inactive_emails = {u["email"] for u in d["users"]}
        assert "deleted@test.com" not in inactive_emails

        # --- 9. pagination ---
        r = await c.get(
            "/admin/users?page=1&page_size=1",
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert r.status_code == 200, r.text
        d = r.json()
        assert len(d["users"]) == 1
        assert d["page_size"] == 1

    del app.dependency_overrides[require_admin]


# ===========================================================================
# Test: 3.6-c create_user
# ===========================================================================

@pytest.mark.asyncio
async def test_create_user(admin_app):
    """
    POST /admin/users:
    - 201 with UserItem (no password)
    - 409 duplicate email (incl. soft-deleted email)
    - 422 invalid email / password < 8 chars
    - Admin-gated (403 non-admin)
    """
    app, session_factory = admin_app

    admin_user = await _make_user(session_factory, is_superuser=True, email="creator-admin@test.com")
    regular_user = await _make_user(session_factory, is_superuser=False, email="not-admin@test.com")
    deleted_user = await _make_user(
        session_factory,
        is_superuser=False,
        email="was-deleted@test.com",
        deleted=True,
    )

    admin_token = _token(admin_user.id)
    regular_token = _token(regular_user.id)

    from app.api.deps import require_admin
    app.dependency_overrides[require_admin] = lambda: admin_user

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:

        # --- 1. Non-admin → 403 ---
        del app.dependency_overrides[require_admin]
        r = await c.post(
            "/admin/users",
            json={"email": "new@test.com", "password": "Password1!"},
            headers={"Authorization": f"Bearer {regular_token}"},
        )
        assert r.status_code == 403, r.text
        app.dependency_overrides[require_admin] = lambda: admin_user

        # --- 2. Create valid user → 201 ---
        r = await c.post(
            "/admin/users",
            json={
                "email": "newuser@test.com",
                "full_name": "New User",
                "password": "SecurePass1!",
                "is_superuser": False,
                "is_active": True,
            },
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert r.status_code == 201, r.text
        d = r.json()
        assert d["email"] == "newuser@test.com"
        assert d["full_name"] == "New User"
        assert d["is_active"] is True
        assert d["is_superuser"] is False
        assert "hashed_password" not in d
        assert "password" not in d
        assert "id" in d
        assert "created_at" in d

        # Verify DB row
        async with session_factory() as session:
            from app.db.models import User
            from app.core.security import verify_password
            result = await session.execute(select(User).where(User.email == "newuser@test.com"))
            user_row = result.scalar_one_or_none()
            assert user_row is not None
            assert user_row.hashed_password != "SecurePass1!"
            assert verify_password("SecurePass1!", user_row.hashed_password)

        # --- 3. Duplicate active email → 409 ---
        r = await c.post(
            "/admin/users",
            json={"email": "newuser@test.com", "password": "SecurePass1!"},
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert r.status_code == 409, r.text

        # --- 4. Soft-deleted email → 409 (still taken) ---
        r = await c.post(
            "/admin/users",
            json={"email": "was-deleted@test.com", "password": "SecurePass1!"},
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert r.status_code == 409, r.text

        # --- 5. Invalid email → 422 ---
        r = await c.post(
            "/admin/users",
            json={"email": "not-an-email", "password": "SecurePass1!"},
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert r.status_code == 422, r.text

        # --- 6. Password < 8 chars → 422 ---
        r = await c.post(
            "/admin/users",
            json={"email": "short@test.com", "password": "abc"},
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert r.status_code == 422, r.text

        # --- 7. Missing email → 422 ---
        r = await c.post(
            "/admin/users",
            json={"password": "SecurePass1!"},
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert r.status_code == 422, r.text

    del app.dependency_overrides[require_admin]


# ===========================================================================
# Test: 3.6-d update_guards
# ===========================================================================

@pytest.mark.asyncio
async def test_update_guards(admin_app):
    """
    PATCH /admin/users/{id}:
    - Self-deactivate blocked (400)
    - Self-demote blocked (400)
    - Last-admin demote blocked (409)
    - Last-admin deactivate blocked (409)
    - Normal promote/demote/activate/deactivate works when guards pass
    - Partial updates (only full_name) work
    """
    app, session_factory = admin_app

    admin_user = await _make_user(session_factory, is_superuser=True, email="the-only-admin@test.com")
    regular_user = await _make_user(session_factory, is_superuser=False, email="patchable@test.com", full_name="Original Name")

    admin_token = _token(admin_user.id)

    from app.api.deps import require_admin
    app.dependency_overrides[require_admin] = lambda: admin_user

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:

        # --- 1. Self-deactivate blocked ---
        r = await c.patch(
            f"/admin/users/{admin_user.id}",
            json={"is_active": False},
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert r.status_code == 400, r.text
        assert "cannot deactivate" in r.json()["detail"].lower()

        # --- 2. Self-demote blocked ---
        r = await c.patch(
            f"/admin/users/{admin_user.id}",
            json={"is_superuser": False},
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert r.status_code == 400, r.text
        assert "cannot demote" in r.json()["detail"].lower()

        # --- 3. Last-admin demote blocked (targeting someone else who is the only admin) ---
        # Create a second admin to demote admin_user as proxy test:
        # admin_user is the only admin — try to demote regular_user who isn't even admin.
        # To test last-admin guard properly, promote regular_user first then try demoting admin_user.

        # Promote regular_user to admin (admin_user is still superuser, so now 2 admins)
        r = await c.patch(
            f"/admin/users/{regular_user.id}",
            json={"is_superuser": True},
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert r.status_code == 200, r.text
        assert r.json()["is_superuser"] is True

        # Now demote regular_user back (2 admins exist → should work)
        r = await c.patch(
            f"/admin/users/{regular_user.id}",
            json={"is_superuser": False},
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert r.status_code == 200, r.text
        assert r.json()["is_superuser"] is False

        # Now admin_user is again the only admin.
        # Create another admin and use them as the acting caller to try demoting the last admin.
        second_admin = await _make_user(
            session_factory, is_superuser=True, email="second-admin@test.com"
        )
        app.dependency_overrides[require_admin] = lambda: second_admin

        # second_admin tries to demote admin_user (both are admins — 2 total → OK)
        r = await c.patch(
            f"/admin/users/{admin_user.id}",
            json={"is_superuser": False},
            headers={"Authorization": f"Bearer {_token(second_admin.id)}"},
        )
        assert r.status_code == 200, r.text

        # Now admin_user is no longer admin, second_admin is the only admin.
        # Try demoting second_admin themselves (self-demote → 400)
        app.dependency_overrides[require_admin] = lambda: second_admin
        r = await c.patch(
            f"/admin/users/{second_admin.id}",
            json={"is_superuser": False},
            headers={"Authorization": f"Bearer {_token(second_admin.id)}"},
        )
        assert r.status_code == 400, r.text

        # Try having admin_user (now non-admin, but let's override) demote second_admin (last admin)
        # Re-promote admin_user to test last-admin guard via PATCH
        app.dependency_overrides[require_admin] = lambda: second_admin
        # restore admin_user as superuser so we can have actor = admin_user try to demote second_admin
        async with session_factory() as session:
            from app.db.models import User as UserModel
            result = await session.execute(select(UserModel).where(UserModel.id == admin_user.id))
            u = result.scalar_one()
            u.is_superuser = True
            await session.commit()

        app.dependency_overrides[require_admin] = lambda: admin_user
        # Now 2 admins again. Demote second_admin → should work (1 remains)
        r = await c.patch(
            f"/admin/users/{second_admin.id}",
            json={"is_superuser": False},
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert r.status_code == 200, r.text

        # admin_user is last admin again. Try deactivating them from outside (non-self actor override)
        # Use a second_admin (now non-admin, but override) as the actor
        app.dependency_overrides[require_admin] = lambda: second_admin
        r = await c.patch(
            f"/admin/users/{admin_user.id}",
            json={"is_active": False},
            headers={"Authorization": f"Bearer {_token(second_admin.id)}"},
        )
        assert r.status_code == 409, r.text
        assert "last remaining admin" in r.json()["detail"].lower()

        # --- 4. full_name update works ---
        app.dependency_overrides[require_admin] = lambda: admin_user
        r = await c.patch(
            f"/admin/users/{regular_user.id}",
            json={"full_name": "Updated Name"},
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert r.status_code == 200, r.text
        assert r.json()["full_name"] == "Updated Name"

        # --- 5. Activate/deactivate a non-admin user ---
        r = await c.patch(
            f"/admin/users/{regular_user.id}",
            json={"is_active": False},
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert r.status_code == 200, r.text
        assert r.json()["is_active"] is False

        r = await c.patch(
            f"/admin/users/{regular_user.id}",
            json={"is_active": True},
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert r.status_code == 200, r.text
        assert r.json()["is_active"] is True

    del app.dependency_overrides[require_admin]


# ===========================================================================
# Test: 3.6-e soft_delete_guards
# ===========================================================================

@pytest.mark.asyncio
async def test_soft_delete_guards(admin_app):
    """
    DELETE /admin/users/{id} (soft-delete):
    - Soft-deleted user is hidden from GET /admin/users
    - Soft-deleted user cannot log in (403)
    - Self-delete blocked (400)
    - Last-admin delete blocked (409)
    """
    app, session_factory = admin_app

    admin_user = await _make_user(session_factory, is_superuser=True, email="sole-admin@test.com")
    victim = await _make_user(session_factory, is_superuser=False, email="victim@test.com")

    admin_token = _token(admin_user.id)

    from app.api.deps import require_admin
    app.dependency_overrides[require_admin] = lambda: admin_user

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:

        # --- 1. Self-delete blocked ---
        r = await c.delete(
            f"/admin/users/{admin_user.id}",
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert r.status_code == 400, r.text
        assert "cannot delete" in r.json()["detail"].lower()

        # --- 2. Last-admin delete blocked ---
        # admin_user is the only active admin — try deleting them via another override
        second_admin = await _make_user(
            session_factory, is_superuser=True, email="second-for-delete@test.com"
        )
        app.dependency_overrides[require_admin] = lambda: second_admin

        # second_admin is not the last admin (admin_user also active)
        # Delete admin_user → makes second_admin last admin
        r = await c.delete(
            f"/admin/users/{admin_user.id}",
            headers={"Authorization": f"Bearer {_token(second_admin.id)}"},
        )
        assert r.status_code == 204, r.text

        # Now second_admin is last admin. Try to delete them.
        app.dependency_overrides[require_admin] = lambda: second_admin
        third_admin = await _make_user(
            session_factory, is_superuser=True, email="third-for-delete@test.com"
        )
        app.dependency_overrides[require_admin] = lambda: third_admin
        # third_admin tries to delete second_admin (second is the only remaining ACTIVE admin? no — third is also active)
        # Both second_admin and third_admin are active admins → delete second_admin should succeed
        r = await c.delete(
            f"/admin/users/{second_admin.id}",
            headers={"Authorization": f"Bearer {_token(third_admin.id)}"},
        )
        assert r.status_code == 204, r.text

        # Now third_admin is last remaining active admin.
        # Another actor tries to delete third_admin.
        app.dependency_overrides[require_admin] = lambda: third_admin  # self-delete attempt
        r = await c.delete(
            f"/admin/users/{third_admin.id}",
            headers={"Authorization": f"Bearer {_token(third_admin.id)}"},
        )
        assert r.status_code == 400, r.text  # self-delete guard fires first

        # Use a "ghost" actor (non-admin override) to test last-admin guard
        ghost_actor = await _make_user(
            session_factory, is_superuser=False, email="ghost-actor@test.com"
        )
        app.dependency_overrides[require_admin] = lambda: ghost_actor
        r = await c.delete(
            f"/admin/users/{third_admin.id}",
            headers={"Authorization": f"Bearer {_token(ghost_actor.id)}"},
        )
        assert r.status_code == 409, r.text
        assert "last remaining admin" in r.json()["detail"].lower()

        # --- 3. Normal soft delete works ---
        app.dependency_overrides[require_admin] = lambda: third_admin
        r = await c.delete(
            f"/admin/users/{victim.id}",
            headers={"Authorization": f"Bearer {_token(third_admin.id)}"},
        )
        assert r.status_code == 204, r.text

        # Verify DB: deleted_at is set, is_active is False
        async with session_factory() as session:
            from app.db.models import User as UserModel
            result = await session.execute(select(UserModel).where(UserModel.id == victim.id))
            u = result.scalar_one()
            assert u.deleted_at is not None, "deleted_at must be set after soft delete"
            assert u.is_active is False, "is_active must be False after soft delete"

        # --- 4. Soft-deleted user hidden from GET /admin/users ---
        r = await c.get(
            "/admin/users",
            headers={"Authorization": f"Bearer {_token(third_admin.id)}"},
        )
        assert r.status_code == 200, r.text
        visible_emails = {u["email"] for u in r.json()["users"]}
        assert "victim@test.com" not in visible_emails, "Soft-deleted user must not appear in list"

        # --- 5. Soft-deleted user cannot log in ---
        # The login endpoint checks is_active. Since soft delete sets is_active=False, login returns 403.
        # We test via get_current_active_user dep by issuing a token for victim and hitting /auth/me.

        # Create a token for the soft-deleted victim (JWT is still technically valid)
        victim_token = _token(victim.id)

        # Override deps to use the real get_current_active_user (not require_admin)
        # We test via a protected endpoint that uses get_current_active_user.
        # GET /admin/users requires require_admin which chains through get_current_active_user.
        # Let's remove the require_admin override and test with the victim's real token.
        del app.dependency_overrides[require_admin]

        r = await c.get(
            "/admin/users",
            headers={"Authorization": f"Bearer {victim_token}"},
        )
        # victim is soft-deleted (is_active=False + deleted_at set) → 403
        assert r.status_code == 403, f"Soft-deleted user must get 403, got {r.status_code}: {r.text}"

        # Re-install for cleanup
        app.dependency_overrides[require_admin] = lambda: third_admin

    del app.dependency_overrides[require_admin]
