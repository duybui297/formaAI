"""Entitlement resolver and enforcement helpers (TASK-3.7).

Public API:
    resolve_entitlements(user, session) -> TierEntitlement | None
    count_monthly_jobs(user_id, session) -> int
"""
from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Job, License, LicenseStatus, LicenseTier, User
from app.licensing.plans import ENTITLEMENTS, TierEntitlement, _TIER_RANK


async def resolve_entitlements(
    user: User,
    session: AsyncSession,
) -> TierEntitlement | None:
    """Return the TierEntitlement for the user's highest-tier ACTIVE license.

    Rules (in priority order):
    1. Superusers always get ENTERPRISE entitlements (no license row required).
    2. Among the user's ACTIVE licenses, pick the highest tier
       (ENTERPRISE > PRO > TRIAL) and return its entitlement.
    3. No ACTIVE licenses → return None.
    """
    if user.is_superuser:
        return ENTITLEMENTS[LicenseTier.ENTERPRISE]

    result = await session.execute(
        select(License.tier)
        .where(
            License.customer_id == str(user.id),
            License.status == LicenseStatus.ACTIVE,
        )
    )
    tiers: list[LicenseTier] = list(result.scalars().all())

    if not tiers:
        return None

    # Pick the tier with the highest rank, skipping any unrecognized tiers.
    valid_tiers = [t for t in tiers if t in _TIER_RANK]
    if not valid_tiers:
        return None

    best_tier = max(valid_tiers, key=lambda t: _TIER_RANK[t])
    return ENTITLEMENTS[best_tier]


async def count_monthly_jobs(user_id: str, session: AsyncSession) -> int:
    """Count jobs owned by *user_id* created in the current calendar month (UTC)."""
    now = datetime.now(timezone.utc)
    # First moment of the current month in UTC (tz-aware).
    month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)

    result = await session.execute(
        select(func.count(Job.id)).where(
            Job.user_id == user_id,
            Job.created_at >= month_start,
        )
    )
    return result.scalar_one()
