"""
Dashboard summary endpoint — US-2.1.

GET /api/v1/dashboard/summary

Aggregates usage metrics for the current billing period (current calendar month UTC):
- filesTranslated: count of jobs with status='done'
- wordsProcessed: estimated word count from segments of completed jobs
- creditsRemaining: monthly_quota - quota_used (null if unlimited)
- activePlan: tier name or null

60s per-user Redis cache.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any

import structlog
from fastapi import APIRouter, Depends
from redis.asyncio import Redis
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_active_user, get_redis, get_session
from app.db.models import Job, License, LicenseStatus, LicenseTier, Segment, User
from app.licensing.plans import ENTITLEMENTS, TIER_RANK

log = structlog.get_logger()

router = APIRouter(prefix="/dashboard", tags=["dashboard"])

DASHBOARD_CACHE_TTL = 60  # seconds


def _get_billing_period_bounds() -> tuple[datetime, datetime]:
    """Return (start, end) of the current billing period (calendar month, UTC)."""
    now = datetime.now(timezone.utc)
    month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    # Last day of month: go to first of next month and subtract 1 second
    if month_start.month == 12:
        month_end = month_start.replace(year=month_start.year + 1, month=1)
    else:
        month_end = month_start.replace(month=month_start.month + 1)
    return month_start, month_end


async def _compute_summary(
    user_id: str,
    session: AsyncSession,
) -> dict[str, Any]:
    """Query the database and compute dashboard metrics."""
    month_start, month_end = _get_billing_period_bounds()

    # 1. Files translated: count jobs with status='done' in billing period
    files_result = await session.execute(
        select(func.count(Job.id)).where(
            Job.user_id == user_id,
            Job.status == "done",
            Job.created_at >= month_start,
            Job.created_at < month_end,
        )
    )
    files_translated = files_result.scalar_one() or 0

    # 2. Words processed: sum of word counts from segments of completed jobs
    # Approximate words = total characters / 5 (average English word length)
    # Only count segments from jobs completed in the billing period
    words_result = await session.execute(
        select(func.coalesce(func.sum(func.length(Segment.source_text)), 0))
        .join(Job, Job.id == Segment.job_id)
        .where(
            Job.user_id == user_id,
            Job.status == "done",
            Job.created_at >= month_start,
            Job.created_at < month_end,
        )
    )
    total_chars = words_result.scalar_one() or 0
    # Divide by 5 to get approximate word count
    words_processed = max(0, total_chars // 5)

    # 3. Credits remaining: from entitlement resolution
    # Get the user's highest-tier active license
    tier_result = await session.execute(
        select(License.tier)
        .where(
            License.customer_id == user_id,
            License.status == LicenseStatus.ACTIVE,
        )
    )
    tiers: list[LicenseTier] = list(tier_result.scalars().all())

    credits_remaining: int | None = None
    active_plan: str | None = None

    if tiers:
        valid_tiers = [t for t in tiers if t in TIER_RANK]
        if valid_tiers:
            best_tier = max(valid_tiers, key=lambda t: TIER_RANK[t])
            entitlement = ENTITLEMENTS[best_tier]
            active_plan = best_tier.value

            if entitlement.monthly_quota is not None:
                # Count jobs created this month (quota_used)
                quota_used_result = await session.execute(
                    select(func.count(Job.id)).where(
                        Job.user_id == user_id,
                        Job.created_at >= month_start,
                        Job.created_at < month_end,
                    )
                )
                quota_used = quota_used_result.scalar_one() or 0
                credits_remaining = max(0, entitlement.monthly_quota - quota_used)

    return {
        "files_translated": files_translated,
        "words_processed": words_processed,
        "credits_remaining": credits_remaining,
        "active_plan": active_plan,
        "billing_period_start": month_start.isoformat(),
        "billing_period_end": month_end.isoformat(),
    }


@router.get(
    "/summary",
    response_model=dict[str, Any],
    summary="Dashboard summary — US-2.1",
)
async def get_dashboard_summary(
    current_user: User = Depends(get_current_active_user),
    session: AsyncSession = Depends(get_session),
    redis: Redis = Depends(get_redis),
) -> dict[str, Any]:
    """Return aggregated usage metrics for the current billing period.

    Results are cached in Redis for 60 seconds per user.
    Cache key: dashboard:summary:{user_id}
    """
    cache_key = f"dashboard:summary:{current_user.id}"
    user_id = str(current_user.id)

    # Try cache first
    cached = await redis.get(cache_key)
    if cached is not None:
        log.debug("dashboard_summary_cache_hit", user_id=user_id)
        data = json.loads(cached)
        # Add cache metadata for debugging
        data["_cached"] = True
        return data

    log.debug("dashboard_summary_cache_miss", user_id=user_id)

    # Compute fresh data
    summary = await _compute_summary(user_id=user_id, session=session)

    # Cache the result
    await redis.setex(
        cache_key,
        DASHBOARD_CACHE_TTL,
        json.dumps(summary),
    )

    summary["_cached"] = False
    return summary
