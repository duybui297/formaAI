"""
Public license routes — TASK-2.2 + TASK-3.3 + TASK-3.7.

POST /licenses/activate   — activate a PENDING license (public, no auth required)
POST /licenses/checkout   — self-serve checkout (authenticated user, non-admin)
GET  /licenses/me         — caller's entitlement summary (TASK-3.7-b)
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

import structlog
from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_active_user, get_redis, get_session, get_settings
from app.db.models import User
from app.licensing.entitlements import count_monthly_jobs, resolve_entitlements
from app.licensing.plans import get_plan_config
from app.schemas.license import (
    ActivateRequest,
    ActivateResponse,
    CheckoutRequest,
    InternalCreateLicenseRequest,
    LicenseResponse,
    MyLicensesResponse,
    MyLicenseItem,
)
from app.services import license_service

log = structlog.get_logger()

router = APIRouter(prefix="/licenses", tags=["licenses"])


@router.get(
    "/me",
    status_code=status.HTTP_200_OK,
    summary="Caller's entitlement summary (TASK-3.7-b)",
)
async def get_my_entitlements(
    current_user: User = Depends(get_current_active_user),
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    """Return the authenticated user's entitlement summary.

    Response shape:
        {
          has_active: bool,
          tier: str | null,
          max_file_bytes: int | null,
          monthly_quota: int | null,     # null = unlimited
          quota_used: int,               # jobs created this calendar month (UTC)
          ocr_allowed: bool | null,
          glossary_allowed: bool | null,
        }

    A user with no active license returns has_active=false and null/zero for
    all limit fields (still 200 — not an error).
    Superusers return has_active=true with ENTERPRISE entitlements.
    """
    entitlement = await resolve_entitlements(user=current_user, session=session)
    quota_used = await count_monthly_jobs(user_id=str(current_user.id), session=session)

    if entitlement is None:
        return {
            "has_active": False,
            "tier": None,
            "max_file_bytes": None,
            "monthly_quota": None,
            "quota_used": quota_used,
            "ocr_allowed": None,
            "glossary_allowed": None,
        }

    # Determine tier name from entitlement by reverse-looking up ENTITLEMENTS map.
    from app.licensing.plans import ENTITLEMENTS
    from app.db.models import LicenseTier
    tier_name: str | None = None
    for t, e in ENTITLEMENTS.items():
        if e is entitlement or e == entitlement:
            tier_name = t.value
            break

    return {
        "has_active": True,
        "tier": tier_name,
        "max_file_bytes": entitlement.max_file_bytes,
        "monthly_quota": entitlement.monthly_quota,
        "quota_used": quota_used,
        "ocr_allowed": entitlement.ocr_allowed,
        "glossary_allowed": entitlement.glossary_allowed,
    }


@router.get(
    "/my-licenses",
    response_model=MyLicensesResponse,
    status_code=status.HTTP_200_OK,
    summary="List all licenses owned by the authenticated user",
)
async def get_my_licenses(
    current_user: User = Depends(get_current_active_user),
    session: AsyncSession = Depends(get_session),
) -> MyLicensesResponse:
    """Return all licenses belonging to the current user.

    Includes both PENDING (not yet activated) and ACTIVE/EXPIRED/SUSPENDED/REVOKED
    licenses so the user can see:
      - Which licenses are waiting to be activated
      - Status of previously activated licenses

    The raw key is never returned — it is only shown once at creation time.
    A PENDING license that has not been activated cannot be "recovered" by the
    user; they must contact the admin for a new key.

    The `pending_count` field lets the UI show a badge like "1 license pending
    activation" on the sidebar nav item.
    """
    from sqlalchemy import func, select
    from app.db.models import License

    result = await session.execute(
        select(License)
        .where(License.customer_id == str(current_user.id))
        .order_by(License.issued_at.desc())
    )
    licenses = result.scalars().all()

    items = [MyLicenseItem.from_license(lic) for lic in licenses]
    pending_count = sum(
        1 for lic in items if lic.status == "pending"
    )

    return MyLicensesResponse(
        licenses=items,
        total=len(items),
        pending_count=pending_count,
    )


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

    create_req = InternalCreateLicenseRequest(
        tier=plan_cfg.tier,
        customer_id=str(current_user.id),
        max_devices=plan_cfg.max_devices,
        expires_at=expires_at,
    )

    result = await license_service.create_license_checkout(
        session=session,
        request=create_req,
        actor_id=str(current_user.id),
        signing_secret=settings.license_signing_secret.get_secret_value(),
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
