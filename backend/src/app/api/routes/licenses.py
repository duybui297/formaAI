# licenses.py

"""
Public license routes — TASK-2.2 + TASK-3.3.

POST /licenses/activate   — activate a PENDING license (public, no auth required)
POST /licenses/checkout   — self-serve checkout (authenticated user, non-admin)
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

import structlog
from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_active_user, get_redis, get_session, get_settings
from app.db.models import User
from app.licensing.plans import get_plan_config
from app.schemas.license import (
    ActivateRequest,
    ActivateResponse,
    CheckoutRequest,
    CreateLicenseRequest,
    LicenseResponse,
)
from app.services import license_service

log = structlog.get_logger()

router = APIRouter(prefix="/licenses", tags=["licenses"])


@router.post(
    "/checkout",
    response_model=LicenseResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Self-serve checkout — create a license for the current user",
)
async def checkout_license(
    body: CheckoutRequest,
    current_user: User = Depends(get_current_active_user),
    session: AsyncSession = Depends(get_session),
    settings=Depends(get_settings),
) -> LicenseResponse:
    """Create a PENDING license for the authenticated user.

    - Authenticated (non-admin) user only — customer_id is always the current user.
    - Maps plan → LicenseTier, max_devices, validity_days via PLAN_CONFIGS.
    - Calls license_service.create_license (reused from admin path) with
      customer_id = current_user.id.
    - raw_key returned exactly once in the 201 response; never persisted.
    - No idempotency header — each POST mints a new license.
    """
    plan_cfg = get_plan_config(body.plan)

    now = datetime.now(timezone.utc)
    expires_at = now + timedelta(days=plan_cfg.validity_days)

    create_req = CreateLicenseRequest(
        tier=plan_cfg.tier,
        customer_id=current_user.id,
        max_devices=plan_cfg.max_devices,
        expires_at=expires_at,
    )

    result = await license_service.create_license(
        session=session,
        request=create_req,
        actor_id=current_user.id,
        signing_secret=settings.license_signing_secret.get_secret_value(),
        idempotency_key=None,
    )

    log.info(
        "checkout_license_created",
        user_id=current_user.id,
        plan=body.plan,
        tier=plan_cfg.tier.value,
        license_id=result.id,
    )

    return result


@router.post(
    "/activate",
    response_model=ActivateResponse,
    status_code=status.HTTP_200_OK,
    summary="Activate a license key",
)
async def activate_license(
    body: ActivateRequest,
    session: AsyncSession = Depends(get_session),
    redis=Depends(get_redis),
) -> ActivateResponse:
    """Activate a PENDING license.

    - Looks up the license by SHA-256 hash of the supplied raw key.
    - Acquires a distributed Redis lock (NX EX 10) to prevent concurrent
      double-activations of the same key.
    - Sets status=ACTIVE, activated_at=now, expired_at (tier-based default or
      the pre-set expiry from the create call).
    - Writes a Redis cache entry ``license:{key_hash}`` with TTL = expired_at − now.
    - Writes a LicenseActivity ACTIVATED audit row.

    Returns 404 if the key is not found, 409 if activation lock is contended,
    400 if the license is already activated or in an invalid state.
    """
    return await license_service.activate_license(
        session=session,
        redis=redis,
        request=body,
    )
