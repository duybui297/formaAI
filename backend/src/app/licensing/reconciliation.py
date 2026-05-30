"""License expiration reconciliation — TASK-2.4.

arq cron task (2 AM daily): flips ACTIVE licenses with expired_at < now to EXPIRED,
deletes Redis cache keys, writes audit rows, and publishes expiry / 7-day-warning events.

Design decisions:
- Batching: SELECT + UPDATE in windows of `batch_size` rows (default 500); each window
  is committed independently so there is never a single giant transaction.
- Redis cleanup: DEL license:{key_hash} for each expired license (clock-skew safety).
- Event sink: injectable async callable(event_type, license_id, extra) so tests can
  capture events without a real email queue. The worker passes a no-op sink by default;
  production can pass an async publisher.
- now injection: deterministic testing; defaults to datetime.now(timezone.utc).
- tz normalisation: SQLite test DB returns tz-naive datetimes from DateTime(timezone=True)
  columns — we coerce to UTC before comparison.
"""
from __future__ import annotations

import math
import uuid
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Any

import structlog
from redis.asyncio import Redis
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import License, LicenseActivity, LicenseEventType, LicenseStatus

log = structlog.get_logger()

# ---------------------------------------------------------------------------
# Event types published by this reconciler
# ---------------------------------------------------------------------------

EVENT_EXPIRED = "license.expired"
EVENT_WARNING_7D = "license.expiring_soon"  # expires within 7 days

# ---------------------------------------------------------------------------
# Result dataclass
# ---------------------------------------------------------------------------


@dataclass
class ReconcileResult:
    """Summary of one reconciliation run."""

    expired_count: int = 0
    warning_count: int = 0
    batches: int = 0
    events: list[dict[str, Any]] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Helper — coerce naive datetime to UTC
# ---------------------------------------------------------------------------


def _to_utc(dt: datetime) -> datetime:
    """Return dt as UTC-aware.  If dt is tz-naive, assume UTC (SQLite compat)."""
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


# ---------------------------------------------------------------------------
# Core reconciliation function
# ---------------------------------------------------------------------------


async def reconcile_expirations(
    session: AsyncSession,
    redis: Redis,
    *,
    batch_size: int = 500,
    now: datetime | None = None,
    event_sink: Callable[..., Awaitable[None]] | None = None,
) -> ReconcileResult:
    """Mark ACTIVE licenses whose expired_at < now as EXPIRED.

    Parameters
    ----------
    session:
        Async DB session.  The function commits per batch and re-uses the
        same session across batches (session remains open, isolation per
        commit is acceptable for a background cron).
    redis:
        Async Redis client for DEL license:{key_hash} keys.
    batch_size:
        Maximum licenses processed per DB transaction.  Default 500.
        Pass a small value in tests to exercise the batching path.
    now:
        Reference timestamp.  Defaults to datetime.now(timezone.utc).
        Inject a fixed datetime in tests for deterministic results.
    event_sink:
        Async callable ``(event_type: str, license_id: str, **extra) -> None``.
        Called for every expiry and 7-day-warning event.  Defaults to a
        no-op so the function is safe to call without a real event queue.

    Returns
    -------
    ReconcileResult
        Counts of expired licenses, 7-day-warning licenses, batch iterations,
        and the raw event dicts pushed to the sink.
    """
    if now is None:
        now = datetime.now(timezone.utc)
    else:
        now = _to_utc(now)

    if event_sink is None:
        async def event_sink(*_args: Any, **_kwargs: Any) -> None:  # type: ignore[misc]
            pass

    result = ReconcileResult()

    # ------------------------------------------------------------------
    # 1. Flip ACTIVE → EXPIRED in batches
    # ------------------------------------------------------------------
    while True:
        # Fetch next batch of candidates; ORDER BY ensures deterministic paging.
        stmt = (
            select(License)
            .where(
                License.status == LicenseStatus.ACTIVE,
                License.expired_at.is_not(None),
            )
            .order_by(License.expired_at)
            .limit(batch_size)
        )
        rows = (await session.execute(stmt)).scalars().all()

        # Filter in Python: normalise tz-naive expired_at from SQLite.
        # PostgreSQL always returns tz-aware; SQLite may return tz-naive.
        expired_rows = [r for r in rows if _to_utc(r.expired_at) < now]  # type: ignore[arg-type]

        if not expired_rows:
            break

        result.batches += 1

        for lic in expired_rows:
            lic.status = LicenseStatus.EXPIRED
            session.add(lic)

            activity = LicenseActivity(
                id=str(uuid.uuid4()),
                license_id=lic.id,
                event_type=LicenseEventType.EXPIRED,
                actor_id=None,  # system-triggered
                event_metadata={"reconciled_at": now.isoformat()},
            )
            session.add(activity)

            # DEL Redis cache key (clock-skew cleanup)
            cache_key = f"license:{lic.key_hash}"
            await redis.delete(cache_key)

            log.info(
                "license_expired_by_cron",
                license_id=lic.id,
                expired_at=lic.expired_at.isoformat() if lic.expired_at else None,
            )

        await session.commit()
        result.expired_count += len(expired_rows)

        # Publish expiry events AFTER commit so events reflect persisted state.
        for lic in expired_rows:
            event = {
                "type": EVENT_EXPIRED,
                "license_id": lic.id,
                "expired_at": lic.expired_at.isoformat() if lic.expired_at else None,
            }
            result.events.append(event)
            await event_sink(EVENT_EXPIRED, lic.id, expired_at=lic.expired_at)

        # If this batch didn't fill completely we've processed all expired rows.
        if len(expired_rows) < batch_size:
            break

    # ------------------------------------------------------------------
    # 2. Publish 7-day-warning events for licenses expiring within 7 days
    #    (still ACTIVE — not yet expired)
    # ------------------------------------------------------------------
    warning_cutoff = now + timedelta(days=7)
    warn_stmt = (
        select(License)
        .where(
            License.status == LicenseStatus.ACTIVE,
            License.expired_at.is_not(None),
        )
    )
    warn_rows = (await session.execute(warn_stmt)).scalars().all()

    # Filter in Python for SQLite tz compat
    warn_rows_filtered = [
        r
        for r in warn_rows
        if now < _to_utc(r.expired_at) <= _to_utc(warning_cutoff)  # type: ignore[arg-type]
    ]

    for lic in warn_rows_filtered:
        event = {
            "type": EVENT_WARNING_7D,
            "license_id": lic.id,
            "expired_at": lic.expired_at.isoformat() if lic.expired_at else None,
        }
        result.events.append(event)
        await event_sink(EVENT_WARNING_7D, lic.id, expired_at=lic.expired_at)

    result.warning_count = len(warn_rows_filtered)

    log.info(
        "reconcile_expirations_done",
        expired=result.expired_count,
        warnings=result.warning_count,
        batches=result.batches,
    )
    return result
