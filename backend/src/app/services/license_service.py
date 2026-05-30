"""License service — business logic for license management.

TASK-2.1: create_license with idempotency support.
TASK-2.2: activate_license with distributed Redis lock.
"""
from __future__ import annotations

import json
import uuid
from datetime import datetime, timedelta, timezone
from typing import Optional

import structlog
from redis.asyncio import Redis
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import License, LicenseActivity, LicenseEventType, LicenseStatus, LicenseTier
from app.licensing.keygen import generate_license_key, hash_key
from app.schemas.license import ActivateRequest, ActivateResponse, CreateLicenseRequest, LicenseResponse

log = structlog.get_logger()


async def create_license(
    *,
    session: AsyncSession,
    request: CreateLicenseRequest,
    actor_id: str,
    signing_secret: str,
    idempotency_key: Optional[str] = None,
) -> LicenseResponse:
    """Create a new license and write an audit CREATED row.

    Idempotency
    -----------
    If *idempotency_key* is supplied and a License with that key already exists,
    the existing License is returned without any new insert.  The ``raw_key``
    field is ``None`` in that case (the raw key was only returned at initial
    creation and is not stored).

    Parameters
    ----------
    session:
        Async DB session (caller manages transaction boundary).
    request:
        Validated CreateLicenseRequest.
    actor_id:
        ID of the admin user performing the create (written to LicenseActivity).
    signing_secret:
        Value of ``settings.license_signing_secret.get_secret_value()``.
    idempotency_key:
        Optional caller-supplied Idempotency-Key header value.
    """
    # --- idempotency check ---------------------------------------------------
    if idempotency_key:
        result = await session.execute(
            select(License).where(License.idempotency_key == idempotency_key)
        )
        existing = result.scalar_one_or_none()
        if existing is not None:
            log.info("license_create_idempotent", idempotency_key=idempotency_key, license_id=existing.id)
            return LicenseResponse.model_validate(existing)

    # --- generate key + hash -------------------------------------------------
    raw_key = generate_license_key(signing_secret, request.customer_id)
    key_hash_value = hash_key(raw_key)

    # --- persist License -----------------------------------------------------
    license_row = License(
        key_hash=key_hash_value,
        tier=request.tier,
        status=LicenseStatus.PENDING,
        customer_id=request.customer_id,
        max_devices=request.max_devices,
        expired_at=request.expires_at,
        idempotency_key=idempotency_key,
    )
    session.add(license_row)
    await session.flush()  # assign id without committing

    # --- audit row -----------------------------------------------------------
    activity = LicenseActivity(
        license_id=license_row.id,
        event_type=LicenseEventType.CREATED,
        actor_id=actor_id,
        event_metadata={"tier": request.tier.value, "max_devices": request.max_devices},
    )
    session.add(activity)
    await session.commit()
    await session.refresh(license_row)

    log.info("license_created", license_id=license_row.id, tier=request.tier.value)

    response = LicenseResponse.model_validate(license_row)
    # Return raw key exactly once — never persisted
    response.raw_key = raw_key
    return response


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
        return ActivateResponse(
            id=license_row.id,
            tier=license_row.tier,
            status=LicenseStatus.ACTIVE,
            activated_at=now,
            expired_at=expired_at,
        )

    finally:
        # Always release the lock — only if we still own it (compare token)
        current_token = await redis.get(lock_key)
        if current_token == lock_token:
            await redis.delete(lock_key)
