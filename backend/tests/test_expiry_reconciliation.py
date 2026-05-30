"""Tests for TASK-2.4 — License expiry reconciliation cron.

Verification commands (featurelist.json 2.4-a..d):
  pytest tests/test_expiry_reconciliation.py -k flips_expired_to_expired -q
  pytest tests/test_expiry_reconciliation.py -k batches_of_500 -q
  pytest tests/test_expiry_reconciliation.py -k deletes_redis_keys -q
  pytest tests/test_expiry_reconciliation.py -k publishes_expiry_events -q

All tests use a real SQLite in-memory DB (from conftest test_engine) and
fakeredis so no external services are required.  No mocks, no skips.
"""
from __future__ import annotations

import math
import uuid
from datetime import datetime, timedelta, timezone

import fakeredis.aioredis as fakeredis_async
import pytest
import pytest_asyncio
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker

from app.db.models import (
    Base,
    License,
    LicenseActivity,
    LicenseEventType,
    LicenseStatus,
    LicenseTier,
    User,
)
from app.licensing.reconciliation import (
    EVENT_EXPIRED,
    EVENT_WARNING_7D,
    reconcile_expirations,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_NOW = datetime(2026, 6, 1, 2, 0, 0, tzinfo=timezone.utc)


def _make_user_obj() -> User:
    return User(
        id=str(uuid.uuid4()),
        email=f"{uuid.uuid4().hex[:8]}@example.com",
        hashed_password="$2b$12$placeholder",
        is_active=True,
        is_superuser=False,
        email_verified=True,
    )


def _make_license(
    customer_id: str,
    *,
    status: LicenseStatus = LicenseStatus.ACTIVE,
    expired_at: datetime | None = None,
    key_hash: str | None = None,
) -> License:
    return License(
        id=str(uuid.uuid4()),
        key_hash=key_hash or uuid.uuid4().hex * 2,  # 64-char hex
        tier=LicenseTier.PRO,
        status=status,
        customer_id=customer_id,
        max_devices=1,
        expired_at=expired_at,
    )


# ---------------------------------------------------------------------------
# Per-test fixtures using the session-scoped test_engine from conftest
# ---------------------------------------------------------------------------


@pytest_asyncio.fixture
async def session_factory(test_engine):
    """async_sessionmaker wrapping the shared in-memory SQLite engine."""
    return async_sessionmaker(test_engine, expire_on_commit=False)


@pytest_asyncio.fixture
async def fake_redis():
    """Isolated fakeredis instance per test, decode_responses=True (matches worker)."""
    r = fakeredis_async.FakeRedis(decode_responses=True)
    yield r
    await r.aclose()


@pytest_asyncio.fixture
async def customer(session_factory):
    """A single committed User row reused across tests."""
    user = _make_user_obj()
    async with session_factory() as s:
        s.add(user)
        await s.commit()
    return user


# ---------------------------------------------------------------------------
# 2.4-a: flips ACTIVE licenses with expired_at < now to EXPIRED
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_flips_expired_to_expired(session_factory, fake_redis, customer):
    """ACTIVE licenses with expired_at < now become EXPIRED; future ones stay ACTIVE.

    Verifies:
    - Status transition ACTIVE → EXPIRED for past-due licenses.
    - Status unchanged for licenses with future expired_at.
    - LicenseActivity EXPIRED row written for each flipped license.
    """
    past = _NOW - timedelta(days=1)
    future = _NOW + timedelta(days=30)

    lic_past = _make_license(customer.id, expired_at=past)
    lic_future = _make_license(customer.id, expired_at=future)

    async with session_factory() as s:
        s.add_all([lic_past, lic_future])
        await s.commit()

    async with session_factory() as s:
        result = await reconcile_expirations(s, fake_redis, now=_NOW)

    assert result.expired_count == 1

    async with session_factory() as s:
        refreshed_past = await s.get(License, lic_past.id)
        refreshed_future = await s.get(License, lic_future.id)

        assert refreshed_past is not None
        assert refreshed_past.status == LicenseStatus.EXPIRED

        assert refreshed_future is not None
        assert refreshed_future.status == LicenseStatus.ACTIVE

        # Verify audit row written
        activity_rows = (
            await s.execute(
                select(LicenseActivity).where(
                    LicenseActivity.license_id == lic_past.id,
                    LicenseActivity.event_type == LicenseEventType.EXPIRED,
                )
            )
        ).scalars().all()
        assert len(activity_rows) == 1, "Expected exactly one EXPIRED activity row"

        # No activity written for the still-active license
        future_activity = (
            await s.execute(
                select(LicenseActivity).where(
                    LicenseActivity.license_id == lic_future.id,
                    LicenseActivity.event_type == LicenseEventType.EXPIRED,
                )
            )
        ).scalars().all()
        assert len(future_activity) == 0


# ---------------------------------------------------------------------------
# 2.4-b: bulk update processed in batches of 500
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_batches_of_500(session_factory, fake_redis, customer):
    """Reconciliation processes rows in windows of batch_size, not one giant transaction.

    Seed 5 expired licenses, run with batch_size=2.
    Expected: ceil(5/2) = 3 batch iterations, all 5 licenses EXPIRED.

    Proves the batching loop executes multiple commits rather than a single
    mega-transaction. result.batches is the authoritative counter.
    """
    n = 5
    batch_size = 2
    past = _NOW - timedelta(days=1)

    licenses = [_make_license(customer.id, expired_at=past) for _ in range(n)]
    async with session_factory() as s:
        s.add_all(licenses)
        await s.commit()

    async with session_factory() as s:
        result = await reconcile_expirations(s, fake_redis, batch_size=batch_size, now=_NOW)

    expected_batches = math.ceil(n / batch_size)
    assert result.expired_count == n, f"Expected {n} expired, got {result.expired_count}"
    assert result.batches == expected_batches, (
        f"Expected {expected_batches} batches (ceil({n}/{batch_size})), "
        f"got {result.batches}"
    )

    async with session_factory() as s:
        for lic in licenses:
            refreshed = await s.get(License, lic.id)
            assert refreshed is not None
            assert refreshed.status == LicenseStatus.EXPIRED, (
                f"License {lic.id} should be EXPIRED"
            )


# ---------------------------------------------------------------------------
# 2.4-c: Redis keys license:{key_hash} for expired licenses are deleted
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_deletes_redis_keys(session_factory, fake_redis, customer):
    """Redis cache key license:{key_hash} is DELeted for expired licenses.

    A still-active license's key is preserved.
    """
    past = _NOW - timedelta(hours=1)
    future = _NOW + timedelta(days=10)

    lic_expired = _make_license(customer.id, expired_at=past)
    lic_active = _make_license(customer.id, expired_at=future)

    async with session_factory() as s:
        s.add_all([lic_expired, lic_active])
        await s.commit()

    # Pre-seed Redis with both keys
    expired_cache_key = f"license:{lic_expired.key_hash}"
    active_cache_key = f"license:{lic_active.key_hash}"
    await fake_redis.set(expired_cache_key, '{"status":"ACTIVE"}')
    await fake_redis.set(active_cache_key, '{"status":"ACTIVE"}')

    async with session_factory() as s:
        await reconcile_expirations(s, fake_redis, now=_NOW)

    # Expired license's key must be gone
    expired_val = await fake_redis.get(expired_cache_key)
    assert expired_val is None, (
        f"Expected Redis key {expired_cache_key!r} to be deleted, but it still exists"
    )

    # Still-active license's key must remain untouched
    active_val = await fake_redis.get(active_cache_key)
    assert active_val is not None, (
        f"Expected Redis key {active_cache_key!r} to be preserved, but it was deleted"
    )


# ---------------------------------------------------------------------------
# 2.4-d: expiry / 7-day-warning events published
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_publishes_expiry_events(session_factory, fake_redis, customer):
    """Events captured via injected sink:
    - EVENT_EXPIRED for the newly-expired license.
    - EVENT_WARNING_7D for a license expiring within 7 days (still ACTIVE).
    """
    past = _NOW - timedelta(hours=2)
    soon = _NOW + timedelta(days=3)   # within 7-day warning window
    far = _NOW + timedelta(days=60)   # outside 7-day window

    lic_expired = _make_license(customer.id, expired_at=past)
    lic_warning = _make_license(customer.id, expired_at=soon)
    lic_safe = _make_license(customer.id, expired_at=far)

    async with session_factory() as s:
        s.add_all([lic_expired, lic_warning, lic_safe])
        await s.commit()

    # Capture all events via an injectable async sink
    captured: list[dict] = []

    async def _sink(event_type: str, license_id: str, **_kwargs) -> None:
        captured.append({"type": event_type, "license_id": license_id})

    async with session_factory() as s:
        result = await reconcile_expirations(s, fake_redis, now=_NOW, event_sink=_sink)

    # 1 expiry event for lic_expired
    expiry_events = [e for e in captured if e["type"] == EVENT_EXPIRED]
    assert len(expiry_events) == 1, f"Expected 1 expiry event, got {expiry_events}"
    assert expiry_events[0]["license_id"] == lic_expired.id

    # 1 warning event for lic_warning (expires in 3 days, inside 7-day window)
    warning_events = [e for e in captured if e["type"] == EVENT_WARNING_7D]
    warning_ids = {e["license_id"] for e in warning_events}
    assert lic_warning.id in warning_ids, (
        f"Expected warning event for {lic_warning.id}, got {warning_events}"
    )

    # lic_safe (60 days out) must NOT appear in warning events
    assert lic_safe.id not in warning_ids, (
        f"License expiring in 60 days should not generate a 7-day warning"
    )

    # result counts match
    assert result.expired_count == 1
    assert result.warning_count == 1


# ---------------------------------------------------------------------------
# 4.1-d: reconciliation — selected by -k reconciliation
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_reconciliation_flips_injected_expired(session_factory, fake_redis, customer):
    """Injecting a fixed 'now' drives reconciliation deterministically.

    Seeds two ACTIVE licenses:
    - lic_expired: expired_at = injected_now - 1s  → must flip to EXPIRED
    - lic_active:  expired_at = injected_now + 1h  → must remain ACTIVE

    The injected 'now' is passed directly to reconcile_expirations so there is
    no dependency on real wall-clock time.  Proves the injectable clock controls
    which licenses are considered expired.
    """
    injected_now = datetime(2030, 1, 1, 0, 0, 0, tzinfo=timezone.utc)

    expired_at_past = injected_now - timedelta(seconds=1)
    expired_at_future = injected_now + timedelta(hours=1)

    lic_expired = _make_license(customer.id, expired_at=expired_at_past)
    lic_active = _make_license(customer.id, expired_at=expired_at_future)

    async with session_factory() as s:
        s.add_all([lic_expired, lic_active])
        await s.commit()

    async with session_factory() as s:
        result = await reconcile_expirations(s, fake_redis, now=injected_now)

    # The shared SQLite DB may contain expired licenses from other tests;
    # assert on the specific licenses we seeded rather than on total count.
    assert result.expired_count >= 1, (
        f"Expected at least 1 license expired, got {result.expired_count}"
    )

    async with session_factory() as s:
        refreshed_expired = await s.get(License, lic_expired.id)
        refreshed_active = await s.get(License, lic_active.id)

        assert refreshed_expired is not None
        assert refreshed_expired.status == LicenseStatus.EXPIRED, (
            f"License with expired_at < injected_now should be EXPIRED, "
            f"got {refreshed_expired.status}"
        )

        assert refreshed_active is not None
        assert refreshed_active.status == LicenseStatus.ACTIVE, (
            f"License with expired_at > injected_now should stay ACTIVE, "
            f"got {refreshed_active.status}"
        )
