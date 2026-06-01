"""License service — business logic for license management.

TASK-2.1: create_license with idempotency support.
TASK-2.2: activate_license with distributed Redis lock.
TASK-2.5: list/get/activities/suspend/revoke/extend admin operations.
"""
from __future__ import annotations

import json
import uuid
from datetime import datetime, timedelta, timezone
from typing import Optional

import structlog
from redis.asyncio import Redis
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import License, LicenseActivity, LicenseEventType, LicenseStatus, LicenseTier, User
from app.licensing.keygen import generate_license_key, hash_key
from app.licensing.plans import get_tier_features
from app.schemas.license import (
    ActivateRequest,
    ActivateResponse,
    BulkIdsRequest,
    ExtendRequest,
    FECreateLicenseResponse,
    InternalCreateLicenseRequest,
    LicenseActivityFEResponse,
    LicenseAdminResponse,
    LicenseListResponse,
    LicenseResponse,
)

log = structlog.get_logger()


async def _resolve_email_to_user(
    session: AsyncSession,
    email: str,
) -> User:
    """Look up a User by email (case-insensitive).  Raises HTTPException 400 if not found."""
    from fastapi import HTTPException, status as http_status

    result = await session.execute(
        select(User).where(func.lower(User.email) == email.lower())
    )
    user = result.scalar_one_or_none()
    if user is None:
        raise HTTPException(
            status_code=http_status.HTTP_400_BAD_REQUEST,
            detail=f"No user found with email {email!r}",
        )
    return user


async def _fetch_email_for_id(
    session: AsyncSession,
    user_id: Optional[str],
) -> Optional[str]:
    """Return email for a user_id, or None if user_id is None / not found."""
    if not user_id:
        return None
    result = await session.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    return user.email if user else None


async def _fetch_emails_for_ids(
    session: AsyncSession,
    user_ids: list[str],
) -> dict[str, str]:
    """Batch-fetch email for a list of user_ids.  Returns {user_id: email}."""
    if not user_ids:
        return {}
    result = await session.execute(select(User).where(User.id.in_(user_ids)))
    users = result.scalars().all()
    return {u.id: u.email for u in users}


async def _create_license_row(
    *,
    session: AsyncSession,
    request: InternalCreateLicenseRequest,
    actor_id: str,
    signing_secret: str,
    idempotency_key: Optional[str] = None,
) -> tuple[License, Optional[str]]:
    """Core DB work: persist a License + audit row, return (license_row, raw_key).

    raw_key is None when an idempotency hit returns an existing row.
    Callers are responsible for shaping the final HTTP response.
    """
    customer_uuid = request.customer_id

    # --- idempotency check ---------------------------------------------------
    if idempotency_key:
        result = await session.execute(
            select(License).where(License.idempotency_key == idempotency_key)
        )
        existing = result.scalar_one_or_none()
        if existing is not None:
            log.info(
                "license_create_idempotent",
                idempotency_key=idempotency_key,
                license_id=existing.id,
            )
            return existing, None

    be_tier = request.tier
    expires_at = request.expires_at
    max_devices = request.max_devices if request.max_devices is not None else 1

    raw_key = generate_license_key(signing_secret, customer_uuid)
    key_hash_value = hash_key(raw_key)

    license_row = License(
        key_hash=key_hash_value,
        tier=be_tier,
        status=LicenseStatus.PENDING,
        customer_id=customer_uuid,
        max_devices=max_devices,
        expired_at=expires_at,
        idempotency_key=idempotency_key,
    )
    session.add(license_row)
    await session.flush()

    activity = LicenseActivity(
        license_id=license_row.id,
        event_type=LicenseEventType.CREATED,
        actor_id=actor_id,
        event_metadata={"tier": be_tier.value, "max_devices": max_devices},
    )
    session.add(activity)
    await session.commit()
    await session.refresh(license_row)

    log.info("license_created", license_id=license_row.id, tier=be_tier.value)
    return license_row, raw_key


async def create_license(
    *,
    session: AsyncSession,
    request: InternalCreateLicenseRequest,
    actor_id: str,
    signing_secret: str,
    idempotency_key: Optional[str] = None,
) -> FECreateLicenseResponse:
    """Create a license — returns the FE-vocab nested response used by the admin route.

    FE contract (TASK-2.1-e):
      - request.tier is a BE LicenseTier enum (already resolved by admin route)
      - request.customer_id is a UUID string (already resolved by admin route)
      - Response: { license: LicenseAdminResponse (FE vocab), raw_key: str | None }

    Idempotency: same as _create_license_row.
    """
    license_row, raw_key = await _create_license_row(
        session=session,
        request=request,
        actor_id=actor_id,
        signing_secret=signing_secret,
        idempotency_key=idempotency_key,
    )
    customer_email = await _fetch_email_for_id(session, license_row.customer_id)
    return FECreateLicenseResponse(
        license=LicenseAdminResponse.from_license(license_row, customer_email=customer_email),
        raw_key=raw_key,
    )


async def create_license_checkout(
    *,
    session: AsyncSession,
    request: InternalCreateLicenseRequest,
    actor_id: str,
    signing_secret: str,
) -> LicenseResponse:
    """Create a license for self-serve checkout — returns the flat LicenseResponse.

    Used by POST /licenses/checkout (TASK-3.3).
    No idempotency key (each checkout POST mints a fresh license).
    customer_id in the response is the UUID (not email).
    tier/status are BE enum values (not FE vocab).
    """
    license_row, raw_key = await _create_license_row(
        session=session,
        request=request,
        actor_id=actor_id,
        signing_secret=signing_secret,
        idempotency_key=None,
    )
    return LicenseResponse(
        id=license_row.id,
        tier=license_row.tier,
        status=license_row.status,
        customer_id=license_row.customer_id,
        max_devices=license_row.max_devices,
        issued_at=license_row.issued_at,
        activated_at=license_row.activated_at,
        expired_at=license_row.expired_at,
        created_at=license_row.created_at,
        updated_at=license_row.updated_at,
        raw_key=raw_key,
    )


# ---------------------------------------------------------------------------
# Default validity by tier (used when License.expired_at is None at activation)
# ---------------------------------------------------------------------------
_TIER_VALIDITY_DAYS: dict[LicenseTier, int] = {
    LicenseTier.TRIAL: 30,
    LicenseTier.PRO: 365,
    LicenseTier.ENTERPRISE: 730,
}


async def activate_license(
    *,
    session: AsyncSession,
    redis: Redis,
    request: ActivateRequest,
) -> ActivateResponse:
    """Activate a PENDING license using a distributed Redis lock.

    Flow
    ----
    1. Hash raw key → look up License by key_hash (404 if not found).
    2. Acquire ``SET lock:activate:{key_hash} {token} NX EX 10``.
       If not acquired → 409 (concurrent activation in progress).
    3. Inside lock: re-read status from DB (double-checked locking).
       - PENDING → set activated_at, expired_at, status=ACTIVE; write ACTIVATED audit row.
       - Any other status → 400 (already activated or invalid state).
    4. On success: write ``SET license:{key_hash} {json} EX {ttl}`` cache entry.
    5. ALWAYS release the lock in a finally block (only if we still own the token).

    Raw key is never persisted.
    """
    from fastapi import HTTPException, status as http_status

    key_hash_value = hash_key(request.raw_key)

    # --- look up license by key_hash -----------------------------------------
    result = await session.execute(
        select(License).where(License.key_hash == key_hash_value)
    )
    license_row = result.scalar_one_or_none()
    if license_row is None:
        raise HTTPException(
            status_code=http_status.HTTP_404_NOT_FOUND,
            detail="License key not found",
        )

    # --- acquire distributed lock --------------------------------------------
    lock_key = f"lock:activate:{key_hash_value}"
    lock_token = uuid.uuid4().hex
    acquired = await redis.set(lock_key, lock_token, nx=True, ex=10)
    if not acquired:
        raise HTTPException(
            status_code=http_status.HTTP_409_CONFLICT,
            detail="Activation already in progress — retry shortly",
        )

    try:
        # --- double-checked locking: re-read from DB -------------------------
        await session.refresh(license_row)

        if license_row.status != LicenseStatus.PENDING:
            raise HTTPException(
                status_code=http_status.HTTP_400_BAD_REQUEST,
                detail=f"License cannot be activated: current status is {license_row.status.value}",
            )

        # --- activate --------------------------------------------------------
        now = datetime.now(timezone.utc)

        # Use pre-set expired_at if present; otherwise calculate from tier default.
        # SQLite stores datetimes as timezone-naive; normalise to UTC-aware.
        if license_row.expired_at is not None:
            expired_at = license_row.expired_at
            if expired_at.tzinfo is None:
                expired_at = expired_at.replace(tzinfo=timezone.utc)
        else:
            validity_days = _TIER_VALIDITY_DAYS.get(license_row.tier, 365)
            expired_at = now + timedelta(days=validity_days)

        license_row.status = LicenseStatus.ACTIVE
        license_row.activated_at = now
        license_row.expired_at = expired_at

        activity = LicenseActivity(
            license_id=license_row.id,
            event_type=LicenseEventType.ACTIVATED,
            actor_id=None,  # self-service activation; no human actor
            event_metadata={
                "device_id": request.device_id,
                "activated_at": now.isoformat(),
            },
        )
        session.add(activity)
        await session.commit()
        # Do NOT refresh — activated_at/expired_at are local variables that
        # are authoritative; refresh on SQLite can return stale values when
        # server_default columns are involved (activated_at is nullable so
        # it writes None before the commit flushes in some SQLite sessions).

        # --- write Redis cache -----------------------------------------------
        ttl_seconds = max(0, int((expired_at - now).total_seconds()))
        cache_key = f"license:{key_hash_value}"
        cache_payload = json.dumps(
            {
                "id": license_row.id,
                "tier": license_row.tier.value,
                "status": license_row.status.value,
                "activated_at": now.isoformat(),
                "expired_at": expired_at.isoformat(),
            }
        )
        await redis.set(cache_key, cache_payload, ex=ttl_seconds)

        log.info(
            "license_activated",
            license_id=license_row.id,
            tier=license_row.tier.value,
            expired_at=expired_at.isoformat(),
        )

        # Build response from local variables — the ORM object's activated_at
        # may still reflect the pre-commit state in the current session.
        tier_value = license_row.tier.value  # e.g. "TRIAL", "PRO", "ENTERPRISE"
        return ActivateResponse(
            id=license_row.id,
            tier=tier_value.lower(),              # FE contract: lowercase
            status=LicenseStatus.ACTIVE.value.lower(),  # FE contract: lowercase
            activated_at=now,
            expired_at=expired_at,
            expiry=expired_at.isoformat(),        # FE contract: expiry as ISO string
            features=get_tier_features(tier_value),     # FE contract: feature list
        )

    finally:
        # Always release the lock — only if we still own it (compare token)
        current_token = await redis.get(lock_key)
        if current_token == lock_token:
            await redis.delete(lock_key)


# ---------------------------------------------------------------------------
# TASK-2.5: Admin CRUD operations
# ---------------------------------------------------------------------------

_SORT_COLUMNS: dict[str, object] = {
    "issued_at": None,    # resolved after License import
    "expired_at": None,
    "status": None,
    "tier": None,
}


def _resolve_sort_col(sort_by: str) -> object:
    """Map sort_by string to a SQLAlchemy column expression (default: issued_at)."""
    mapping = {
        "issued_at": License.issued_at,
        "expired_at": License.expired_at,
        "status": License.status,
        "tier": License.tier,
    }
    return mapping.get(sort_by, License.issued_at)


async def list_licenses(
    *,
    session: AsyncSession,
    page: int = 1,
    page_size: int = 20,
    tier: Optional[LicenseTier] = None,
    status: Optional[LicenseStatus] = None,
    search: Optional[str] = None,
    issued_after: Optional[datetime] = None,
    issued_before: Optional[datetime] = None,
    sort_by: str = "issued_at",
    sort_dir: str = "desc",
) -> LicenseListResponse:
    """Return a paginated list of licenses with optional filters.

    tier / status are BE enums (caller decodes FE vocab before calling here).
    Responses have FE-vocab tier/status and email customer_id.
    """
    from sqlalchemy import asc, desc

    query = select(License)

    if tier is not None:
        query = query.where(License.tier == tier)
    if status is not None:
        query = query.where(License.status == status)
    if search:
        query = query.where(
            or_(
                License.key_hash.ilike(f"%{search}%"),
                License.customer_id.ilike(f"%{search}%"),
            )
        )
    if issued_after is not None:
        query = query.where(License.issued_at >= issued_after)
    if issued_before is not None:
        query = query.where(License.issued_at <= issued_before)

    sort_col = _resolve_sort_col(sort_by)
    order_expr = asc(sort_col) if sort_dir == "asc" else desc(sort_col)

    count_query = select(func.count()).select_from(query.subquery())
    total_result = await session.execute(count_query)
    total = total_result.scalar_one()

    offset = (page - 1) * page_size
    rows_result = await session.execute(
        query.order_by(order_expr).offset(offset).limit(page_size)
    )
    rows = rows_result.scalars().all()

    # Batch-resolve customer emails to avoid N+1
    unique_ids = list({r.customer_id for r in rows if r.customer_id})
    email_map = await _fetch_emails_for_ids(session, unique_ids)

    return LicenseListResponse(
        licenses=[
            LicenseAdminResponse.from_license(r, customer_email=email_map.get(r.customer_id))
            for r in rows
        ],
        total=total,
        page=page,
        page_size=page_size,
    )


async def get_license(
    *,
    session: AsyncSession,
    license_id: str,
) -> LicenseAdminResponse:
    """Return full license detail by id (404 if not found)."""
    from fastapi import HTTPException, status as http_status

    lic = await session.get(License, license_id)
    if lic is None:
        raise HTTPException(
            status_code=http_status.HTTP_404_NOT_FOUND,
            detail=f"License {license_id!r} not found",
        )
    email = await _fetch_email_for_id(session, lic.customer_id)
    return LicenseAdminResponse.from_license(lic, customer_email=email)


async def get_license_activities(
    *,
    session: AsyncSession,
    license_id: str,
) -> list[LicenseActivityFEResponse]:
    """Return activity timeline for a license as a bare list, ordered newest-first.

    Returns list[LicenseActivityFEResponse] — no envelope wrapper.
    Raises 404 if the license does not exist.
    """
    from fastapi import HTTPException, status as http_status

    lic = await session.get(License, license_id)
    if lic is None:
        raise HTTPException(
            status_code=http_status.HTTP_404_NOT_FOUND,
            detail=f"License {license_id!r} not found",
        )

    result = await session.execute(
        select(LicenseActivity)
        .where(LicenseActivity.license_id == license_id)
        .order_by(LicenseActivity.created_at.desc())
    )
    activities = result.scalars().all()
    return [LicenseActivityFEResponse.from_activity(a) for a in activities]


async def bulk_suspend_licenses(
    *,
    session: AsyncSession,
    redis: Redis,
    request: BulkIdsRequest,
    actor_id: str,
) -> None:
    """Bulk transition ACTIVE licenses to SUSPENDED.

    For each id in request.ids:
      - If not found: skip (no 500).
      - If already SUSPENDED: raises 409.
      - If not ACTIVE (e.g. PENDING, REVOKED): raises 400.
      - Otherwise: ACTIVE → SUSPENDED, audit row, Redis DEL.

    Empty ids list → 400.
    """
    from fastapi import HTTPException, status as http_status

    if not request.ids:
        raise HTTPException(
            status_code=http_status.HTTP_400_BAD_REQUEST,
            detail="ids must be a non-empty list",
        )

    for license_id in request.ids:
        lic = await session.get(License, license_id)
        if lic is None:
            continue  # skip unknown ids

        if lic.status == LicenseStatus.SUSPENDED:
            raise HTTPException(
                status_code=http_status.HTTP_409_CONFLICT,
                detail=f"License {license_id!r} is already suspended",
            )
        if lic.status != LicenseStatus.ACTIVE:
            raise HTTPException(
                status_code=http_status.HTTP_400_BAD_REQUEST,
                detail=f"Cannot suspend license {license_id!r} with status {lic.status.value}; must be ACTIVE",
            )

        lic.status = LicenseStatus.SUSPENDED
        session.add(
            LicenseActivity(
                license_id=lic.id,
                event_type=LicenseEventType.SUSPENDED,
                actor_id=actor_id,
                event_metadata={"previous_status": LicenseStatus.ACTIVE.value},
            )
        )
        await session.flush()
        cache_key = f"license:{lic.key_hash}"
        await redis.delete(cache_key)
        log.info("license_suspended", license_id=lic.id, actor_id=actor_id)

    await session.commit()


async def bulk_revoke_licenses(
    *,
    session: AsyncSession,
    redis: Redis,
    request: BulkIdsRequest,
    actor_id: str,
) -> None:
    """Bulk transition licenses to REVOKED from any non-REVOKED state.

    For each id in request.ids:
      - If not found: skip.
      - If already REVOKED: raises 409.
      - Otherwise: → REVOKED, audit row, Redis DEL.

    Empty ids list → 400.
    """
    from fastapi import HTTPException, status as http_status

    if not request.ids:
        raise HTTPException(
            status_code=http_status.HTTP_400_BAD_REQUEST,
            detail="ids must be a non-empty list",
        )

    for license_id in request.ids:
        lic = await session.get(License, license_id)
        if lic is None:
            continue  # skip unknown ids

        if lic.status == LicenseStatus.REVOKED:
            raise HTTPException(
                status_code=http_status.HTTP_409_CONFLICT,
                detail=f"License {license_id!r} is already revoked",
            )

        previous_status = lic.status.value
        lic.status = LicenseStatus.REVOKED
        session.add(
            LicenseActivity(
                license_id=lic.id,
                event_type=LicenseEventType.REVOKED,
                actor_id=actor_id,
                event_metadata={"previous_status": previous_status},
            )
        )
        await session.flush()
        cache_key = f"license:{lic.key_hash}"
        await redis.delete(cache_key)
        log.info("license_revoked", license_id=lic.id, actor_id=actor_id)

    await session.commit()


async def extend_license(
    *,
    session: AsyncSession,
    redis: Redis,
    license_id: str,
    actor_id: str,
    request: ExtendRequest,
) -> LicenseAdminResponse:
    """Set expired_at to an absolute datetime value (must be in the future).

    Appends EXTENDED audit row and refreshes Redis TTL to match new expiry.
    Works on licenses in any non-REVOKED status.
    """
    from fastapi import HTTPException, status as http_status

    lic = await session.get(License, license_id)
    if lic is None:
        raise HTTPException(
            status_code=http_status.HTTP_404_NOT_FOUND,
            detail=f"License {license_id!r} not found",
        )

    if lic.status == LicenseStatus.REVOKED:
        raise HTTPException(
            status_code=http_status.HTTP_400_BAD_REQUEST,
            detail="Cannot extend a revoked license",
        )

    now = datetime.now(timezone.utc)
    new_expired_at = request.expired_at
    # Normalise to UTC-aware if tz-naive
    if new_expired_at.tzinfo is None:
        new_expired_at = new_expired_at.replace(tzinfo=timezone.utc)

    if new_expired_at <= now:
        raise HTTPException(
            status_code=http_status.HTTP_400_BAD_REQUEST,
            detail="expired_at must be in the future",
        )

    old_expired_at = lic.expired_at.isoformat() if lic.expired_at else None
    lic.expired_at = new_expired_at
    session.add(
        LicenseActivity(
            license_id=lic.id,
            event_type=LicenseEventType.EXTENDED,
            actor_id=actor_id,
            event_metadata={
                "old_expired_at": old_expired_at,
                "new_expired_at": new_expired_at.isoformat(),
            },
        )
    )
    await session.commit()

    # Refresh Redis cache entry TTL if the license is ACTIVE
    if lic.status == LicenseStatus.ACTIVE:
        ttl_seconds = max(0, int((new_expired_at - now).total_seconds()))
        cache_key = f"license:{lic.key_hash}"
        existing = await redis.get(cache_key)
        if existing:
            try:
                payload = json.loads(existing)
                payload["expired_at"] = new_expired_at.isoformat()
                await redis.set(cache_key, json.dumps(payload), ex=ttl_seconds)
            except (json.JSONDecodeError, Exception):
                # Cache write failure is non-fatal
                await redis.delete(cache_key)

    log.info(
        "license_extended",
        license_id=lic.id,
        actor_id=actor_id,
        new_expired_at=new_expired_at.isoformat(),
    )
    await session.refresh(lic)
    email = await _fetch_email_for_id(session, lic.customer_id)
    return LicenseAdminResponse.from_license(lic, customer_email=email)
