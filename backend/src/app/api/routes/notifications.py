"""
GET /api/v1/notifications — derived user alerts (no persistence required).

Derives from existing data:
- Completed job → "Translation complete" alert
- License expiring within 7 days → "License expiring soon" alert
- No active license → "No active license" alert

Auth: requires valid JWT (get_current_active_user).
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

from fastapi import APIRouter, Depends
from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_active_user, get_session
from app.db.models import Job, License, LicenseStatus, User

router = APIRouter()


def _format_relative_time(dt: datetime) -> str:
    """Return a human-friendly relative time string."""
    now = datetime.now(timezone.utc)
    delta = now - dt

    if delta.total_seconds() < 60:
        return "just now"
    if delta.total_seconds() < 3600:
        minutes = int(delta.total_seconds() / 60)
        return f"{minutes}m ago"
    if delta.total_seconds() < 86400:
        hours = int(delta.total_seconds() / 3600)
        return f"{hours}h ago"
    days = int(delta.total_seconds() / 86400)
    if days == 1:
        return "1d ago"
    return f"{days}d ago"


@router.get("/notifications")
async def get_notifications(
    current_user: User = Depends(get_current_active_user),
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    """Return a list of recent notifications for the current user.

    Notifications are derived (not stored):
    - Recent completed jobs (last 5, newest first)
    - License expiry warnings (within 7 days)
    - Missing active license

    Auth: requires valid JWT (get_current_active_user).
    """
    notifications: list[dict[str, Any]] = []

    # --- 1. Recent completed / failed jobs ---
    result = await session.execute(
        select(Job)
        .where(Job.user_id == current_user.id)
        .order_by(desc(Job.created_at))
        .limit(10)
    )
    recent_jobs = result.scalars().all()

    for job in recent_jobs:
        if job.status.value == "done":
            notifications.append({
                "id": f"job-done-{job.id}",
                "type": "job_complete",
                "title": "Translation complete",
                "description": f"{job.original_filename} is ready for download",
                "time": _format_relative_time(job.created_at) if job.created_at else "recently",
                "job_id": job.id,
                "filename": job.original_filename,
            })
        elif job.status.value == "failed":
            notifications.append({
                "id": f"job-failed-{job.id}",
                "type": "job_failed",
                "title": "Translation failed",
                "description": f"{job.original_filename} could not be translated",
                "time": _format_relative_time(job.created_at) if job.created_at else "recently",
                "job_id": job.id,
                "filename": job.original_filename,
            })

    # --- 2. License expiry warnings ---
    now = datetime.now(timezone.utc)
    expiry_window = now + timedelta(days=7)

    result = await session.execute(
        select(License)
        .where(
            License.customer_id == str(current_user.id),
            License.status == LicenseStatus.ACTIVE,
            License.expired_at != None,  # noqa: E711 (SQLAlchemy None check)
            License.expired_at <= expiry_window,
        )
    )
    expiring = result.scalars().all()

    for lic in expiring:
        if lic.expired_at:
            days_left = (lic.expired_at - now).days
            notifications.append({
                "id": f"license-expiry-{lic.id}",
                "type": "license_expiry",
                "title": "License expiring soon",
                "description": f"Your license expires in {days_left} day{'s' if days_left != 1 else ''}. Contact your admin to extend it.",
                "time": "",
                "license_id": lic.id,
            })

    # --- 3. No active license ---
    result = await session.execute(
        select(License)
        .where(
            License.customer_id == str(current_user.id),
            License.status == LicenseStatus.ACTIVE,
        )
    )
    active_licenses = result.scalars().all()

    if not active_licenses and not current_user.is_superuser:
        notifications.append({
            "id": "no-active-license",
            "type": "no_license",
            "title": "No active license",
            "description": "You don't have an active license. Contact your administrator or visit /pricing.",
            "time": "",
        })

    # Sort by time string (most recent first), expiry/no-license at top
    def sort_key(n: dict[str, Any]) -> tuple[int, str]:
        if n["type"] in ("no_license", "license_expiry"):
            return (0, "")
        time_str = n.get("time", "")
        if "m ago" in time_str:
            return (1, time_str)
        if "h ago" in time_str:
            return (2, time_str)
        if "d ago" in time_str:
            return (3, time_str)
        return (4, time_str)

    notifications.sort(key=sort_key)

    # Limit to 10 most recent
    return {"notifications": notifications[:10]}
