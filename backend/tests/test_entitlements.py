"""
TASK-3.7-a: Unit tests for plans.py ENTITLEMENTS map and resolve_entitlements().

Verification selector: -k tier_entitlements_and_resolver
All test function names include "tier_entitlements_and_resolver" so they match.
"""
from __future__ import annotations

import uuid

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.db.models import Base, LicenseStatus, LicenseTier, User
from app.licensing.plans import ENTITLEMENTS, TierEntitlement

TEST_DB_URL = "sqlite+aiosqlite:///:memory:"


# ---------------------------------------------------------------------------
# Session-scoped engine + function-scoped session
# ---------------------------------------------------------------------------

@pytest_asyncio.fixture(scope="session")
async def engine():
    e = create_async_engine(TEST_DB_URL, echo=False)
    async with e.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield e
    await e.dispose()


@pytest_asyncio.fixture
async def session(engine):
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as s:
        yield s
        await s.rollback()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_user(is_superuser: bool = False) -> User:
    return User(
        id=str(uuid.uuid4()),
        email=f"{uuid.uuid4()}@test.com",
        hashed_password="x",
        is_active=True,
        is_superuser=is_superuser,
    )


async def _seed_license(session: AsyncSession, user: User, tier: LicenseTier, status: LicenseStatus):
    from app.db.models import License
    lic = License(
        id=str(uuid.uuid4()),
        key_hash=str(uuid.uuid4()),
        tier=tier,
        status=status,
        customer_id=str(user.id),
        max_devices=1,
    )
    session.add(lic)
    await session.commit()
    return lic


# ---------------------------------------------------------------------------
# ENTITLEMENTS map value tests — function names match -k tier_entitlements_and_resolver
# ---------------------------------------------------------------------------

def test_tier_entitlements_and_resolver_trial_values():
    """TRIAL entitlement: 5MB, quota=10, ocr=False, glossary=False."""
    e = ENTITLEMENTS[LicenseTier.TRIAL]
    assert isinstance(e, TierEntitlement)
    assert e.max_file_bytes == 5 * 1024 * 1024
    assert e.monthly_quota == 10
    assert e.ocr_allowed is False
    assert e.glossary_allowed is False


def test_tier_entitlements_and_resolver_pro_values():
    """PRO entitlement: 50MB, quota=None, ocr=True, glossary=True."""
    e = ENTITLEMENTS[LicenseTier.PRO]
    assert isinstance(e, TierEntitlement)
    assert e.max_file_bytes == 50 * 1024 * 1024
    assert e.monthly_quota is None
    assert e.ocr_allowed is True
    assert e.glossary_allowed is True


def test_tier_entitlements_and_resolver_enterprise_values():
    """ENTERPRISE entitlement: 100MB, quota=None, ocr=True, glossary=True."""
    e = ENTITLEMENTS[LicenseTier.ENTERPRISE]
    assert isinstance(e, TierEntitlement)
    assert e.max_file_bytes == 100 * 1024 * 1024
    assert e.monthly_quota is None
    assert e.ocr_allowed is True
    assert e.glossary_allowed is True


def test_tier_entitlements_and_resolver_all_tiers_covered():
    """Every LicenseTier must have an ENTITLEMENTS entry."""
    for tier in LicenseTier:
        assert tier in ENTITLEMENTS, f"Missing entitlement for {tier}"


@pytest.mark.asyncio
async def test_tier_entitlements_and_resolver_superuser_gets_enterprise(session):
    """Superuser always gets ENTERPRISE entitlements regardless of licenses."""
    from app.licensing.entitlements import resolve_entitlements

    user = _make_user(is_superuser=True)
    session.add(user)
    await session.flush()

    result = await resolve_entitlements(user=user, session=session)
    assert result is not None
    assert result == ENTITLEMENTS[LicenseTier.ENTERPRISE]


@pytest.mark.asyncio
async def test_tier_entitlements_and_resolver_no_license_returns_none(session):
    """User with no license rows → resolver returns None."""
    from app.licensing.entitlements import resolve_entitlements

    user = _make_user()
    session.add(user)
    await session.flush()

    result = await resolve_entitlements(user=user, session=session)
    assert result is None


@pytest.mark.asyncio
async def test_tier_entitlements_and_resolver_pending_not_active(session):
    """PENDING license is not ACTIVE — resolver returns None."""
    from app.licensing.entitlements import resolve_entitlements

    user = _make_user()
    session.add(user)
    await session.flush()
    await _seed_license(session, user, LicenseTier.TRIAL, LicenseStatus.PENDING)

    result = await resolve_entitlements(user=user, session=session)
    assert result is None


@pytest.mark.asyncio
async def test_tier_entitlements_and_resolver_active_trial(session):
    """Active TRIAL license → TRIAL entitlement returned."""
    from app.licensing.entitlements import resolve_entitlements

    user = _make_user()
    session.add(user)
    await session.flush()
    await _seed_license(session, user, LicenseTier.TRIAL, LicenseStatus.ACTIVE)

    result = await resolve_entitlements(user=user, session=session)
    assert result == ENTITLEMENTS[LicenseTier.TRIAL]


@pytest.mark.asyncio
async def test_tier_entitlements_and_resolver_multi_license_picks_highest(session):
    """User with TRIAL + PRO active → returns PRO (highest tier)."""
    from app.licensing.entitlements import resolve_entitlements

    user = _make_user()
    session.add(user)
    await session.flush()
    await _seed_license(session, user, LicenseTier.TRIAL, LicenseStatus.ACTIVE)
    await _seed_license(session, user, LicenseTier.PRO, LicenseStatus.ACTIVE)

    result = await resolve_entitlements(user=user, session=session)
    assert result == ENTITLEMENTS[LicenseTier.PRO]


@pytest.mark.asyncio
async def test_tier_entitlements_and_resolver_enterprise_beats_pro(session):
    """User with PRO + ENTERPRISE active → returns ENTERPRISE."""
    from app.licensing.entitlements import resolve_entitlements

    user = _make_user()
    session.add(user)
    await session.flush()
    await _seed_license(session, user, LicenseTier.PRO, LicenseStatus.ACTIVE)
    await _seed_license(session, user, LicenseTier.ENTERPRISE, LicenseStatus.ACTIVE)

    result = await resolve_entitlements(user=user, session=session)
    assert result == ENTITLEMENTS[LicenseTier.ENTERPRISE]


@pytest.mark.asyncio
async def test_tier_entitlements_and_resolver_suspended_revoked_ignored(session):
    """SUSPENDED/REVOKED licenses are not counted — resolver returns None."""
    from app.licensing.entitlements import resolve_entitlements

    user = _make_user()
    session.add(user)
    await session.flush()
    await _seed_license(session, user, LicenseTier.ENTERPRISE, LicenseStatus.SUSPENDED)
    await _seed_license(session, user, LicenseTier.PRO, LicenseStatus.REVOKED)

    result = await resolve_entitlements(user=user, session=session)
    assert result is None
