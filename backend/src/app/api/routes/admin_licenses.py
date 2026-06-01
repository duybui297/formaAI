"""
Admin license management routes — TASK-2.1 + TASK-2.5.

Aligned to FE contract (TASK-3.1):

POST   /admin/licenses                    — create a new license (admin only, idempotent via header)
GET    /admin/licenses                    — paginated list with tier/status/issued_after/issued_before/sort_by/sort_dir filters
GET    /admin/licenses/{id}               — full license detail (key_masked)
GET    /admin/licenses/{id}/activities    — activity timeline newest-first (bare array)
POST   /admin/licenses/suspend            — bulk ACTIVE → SUSPENDED; body { ids: [...] }
POST   /admin/licenses/revoke             — bulk any → REVOKED; body { ids: [...] }
POST   /admin/licenses/{id}/extend        — set absolute expired_at; body { expired_at: "<ISO>" }
"""
from __future__ import annotations

from typing import Optional

import structlog
from fastapi import APIRouter, Depends, Header, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_redis, get_settings, require_admin
from app.db.models import User
from app.db.session import get_session
from app.schemas.license import (
    AdminCreateLicenseRequest,
    BulkIdsRequest,
    ExtendRequest,
    FECreateLicenseResponse,
    InternalCreateLicenseRequest,
    LicenseActivityFEResponse,
    LicenseAdminResponse,
    LicenseListResponse,
)
from app.services import license_service

log = structlog.get_logger()

router = APIRouter(prefix="/admin", tags=["admin-licenses"])


@router.post(
    "/licenses",
    response_model=FECreateLicenseResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new license (admin only)",
)
async def create_license(
    body: AdminCreateLicenseRequest,
    idempotency_key: Optional[str] = Header(default=None, alias="Idempotency-Key"),
    current_user: User = Depends(require_admin),
    session: AsyncSession = Depends(get_session),
    settings=Depends(get_settings),
) -> FECreateLicenseResponse:
    """Create a new license.

    FE contract (TASK-2.1-e):
      - body.tier is FE vocab (starter/professional/enterprise)
      - body.customer_id is an EMAIL; unknown email → 400
      - Response: { license: <FE License shape>, raw_key: str | None }
      - raw_key returned exactly once on creation; None on idempotent replay
    """
    from datetime import datetime, timezone

    from app.licensing.vocab import fe_tier_to_be
    from sqlalchemy import func, select
    from app.db.models import User as UserModel

    # Resolve email → user UUID (400 on unknown email)
    result = await session.execute(
        select(UserModel).where(func.lower(UserModel.email) == body.customer_id.lower())
    )
    customer_user = result.scalar_one_or_none()
    if customer_user is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"No user found with email {body.customer_id!r}",
        )

    # Map FE tier → BE enum
    be_tier = fe_tier_to_be(body.tier)

    # Parse optional expired_at string → datetime
    expires_at = None
    if body.expired_at:
        expires_at = datetime.fromisoformat(body.expired_at.replace("Z", "+00:00"))
        if expires_at.tzinfo is None:
            expires_at = expires_at.replace(tzinfo=timezone.utc)

    internal_req = InternalCreateLicenseRequest(
        tier=be_tier,
        customer_id=customer_user.id,
        max_devices=body.max_devices,
        expires_at=expires_at,
    )

    return await license_service.create_license(
        session=session,
        request=internal_req,
        actor_id=current_user.id,
        signing_secret=settings.license_signing_secret.get_secret_value(),
        idempotency_key=idempotency_key,
    )


@router.get(
    "/licenses",
    response_model=LicenseListResponse,
    status_code=status.HTTP_200_OK,
    summary="List licenses with pagination and filters (admin only)",
)
async def list_licenses(
    page: int = Query(default=1, ge=1, description="1-based page number"),
    page_size: int = Query(default=20, ge=1, le=100, description="Items per page"),
    tier: Optional[str] = Query(
        default=None,
        description="Filter by FE tier: starter | professional | enterprise",
    ),
    license_status: Optional[str] = Query(
        default=None,
        alias="status",
        description="Filter by FE status: active | suspended | revoked | expired | pending",
    ),
    search: Optional[str] = Query(
        default=None, description="Substring search on key_hash or customer_id"
    ),
    issued_after: Optional[str] = Query(
        default=None, description="Filter issued_at >= this ISO datetime"
    ),
    issued_before: Optional[str] = Query(
        default=None, description="Filter issued_at <= this ISO datetime"
    ),
    sort_by: str = Query(
        default="issued_at",
        description="Sort column: issued_at | expired_at | status | tier",
    ),
    sort_dir: str = Query(default="desc", description="asc or desc"),
    current_user: User = Depends(require_admin),
    session: AsyncSession = Depends(get_session),
) -> LicenseListResponse:
    """Paginated license list.  Response envelope key is 'licenses' (FE contract).

    Query params *tier* and *status* accept FE vocab strings and are decoded to BE
    enums before filtering.  Unknown values return 400.
    """
    from datetime import datetime, timezone

    from app.db.models import LicenseStatus, LicenseTier
    from app.licensing.vocab import fe_status_to_be, fe_tier_to_be

    # --- decode FE tier/status → BE enum -------------------------------------
    be_tier: Optional[LicenseTier] = None
    if tier:
        # Also accept BE enum values for backwards-compat (e.g. ?tier=PRO)
        try:
            be_tier = fe_tier_to_be(tier)
        except ValueError:
            # Try direct BE enum lookup
            try:
                be_tier = LicenseTier(tier.upper())
            except ValueError:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Unknown tier {tier!r}. Use: starter, professional, enterprise",
                )

    be_status: Optional[LicenseStatus] = None
    if license_status:
        try:
            be_status = fe_status_to_be(license_status)
        except ValueError:
            try:
                be_status = LicenseStatus(license_status.upper())
            except ValueError:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Unknown status {license_status!r}. Use: active, suspended, revoked, expired, pending",
                )

    def _parse_dt(s: Optional[str]):
        if not s:
            return None
        # Query-string decodes '+' as ' ' — restore before parsing
        normalised = s.strip().replace(" ", "+")
        # Handle trailing 'Z'
        normalised = normalised.replace("Z", "+00:00")
        dt = datetime.fromisoformat(normalised)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt

    return await license_service.list_licenses(
        session=session,
        page=page,
        page_size=page_size,
        tier=be_tier,
        status=be_status,
        search=search,
        issued_after=_parse_dt(issued_after),
        issued_before=_parse_dt(issued_before),
        sort_by=sort_by,
        sort_dir=sort_dir,
    )


@router.get(
    "/licenses/{license_id}",
    response_model=LicenseAdminResponse,
    status_code=status.HTTP_200_OK,
    summary="Get full license detail (admin only)",
)
async def get_license(
    license_id: str,
    current_user: User = Depends(require_admin),
    session: AsyncSession = Depends(get_session),
) -> LicenseAdminResponse:
    """Return full license detail.  key_masked is ****-****-****-XXXX; raw key is never returned."""
    return await license_service.get_license(session=session, license_id=license_id)


@router.get(
    "/licenses/{license_id}/activities",
    response_model=list[LicenseActivityFEResponse],
    status_code=status.HTTP_200_OK,
    summary="Get license activity timeline (admin only)",
)
async def get_license_activities(
    license_id: str,
    current_user: User = Depends(require_admin),
    session: AsyncSession = Depends(get_session),
) -> list[LicenseActivityFEResponse]:
    """Return the activity timeline for a license as a bare JSON array, ordered newest-first.

    Each item has: id, license_id, action, actor, detail, created_at.
    """
    return await license_service.get_license_activities(
        session=session, license_id=license_id
    )


# NOTE: /suspend and /revoke must be registered BEFORE /{license_id}/... routes
# so FastAPI does not treat "suspend"/"revoke" as path parameters.

@router.post(
    "/licenses/suspend",
    status_code=status.HTTP_200_OK,
    summary="Bulk suspend licenses (admin only)",
)
async def bulk_suspend_licenses(
    body: BulkIdsRequest,
    current_user: User = Depends(require_admin),
    session: AsyncSession = Depends(get_session),
    redis=Depends(get_redis),
) -> dict:
    """Bulk transition ACTIVE licenses to SUSPENDED.  FE ignores response body."""
    await license_service.bulk_suspend_licenses(
        session=session,
        redis=redis,
        request=body,
        actor_id=current_user.id,
    )
    return {"ok": True}


@router.post(
    "/licenses/revoke",
    status_code=status.HTTP_200_OK,
    summary="Bulk revoke licenses (admin only)",
)
async def bulk_revoke_licenses(
    body: BulkIdsRequest,
    current_user: User = Depends(require_admin),
    session: AsyncSession = Depends(get_session),
    redis=Depends(get_redis),
) -> dict:
    """Bulk transition licenses to REVOKED.  FE ignores response body."""
    await license_service.bulk_revoke_licenses(
        session=session,
        redis=redis,
        request=body,
        actor_id=current_user.id,
    )
    return {"ok": True}


@router.post(
    "/licenses/{license_id}/extend",
    response_model=LicenseAdminResponse,
    status_code=status.HTTP_200_OK,
    summary="Extend a license expiry (admin only)",
)
async def extend_license(
    license_id: str,
    body: ExtendRequest,
    current_user: User = Depends(require_admin),
    session: AsyncSession = Depends(get_session),
    redis=Depends(get_redis),
) -> LicenseAdminResponse:
    """Set expired_at to the given absolute datetime.  Refreshes Redis TTL."""
    return await license_service.extend_license(
        session=session,
        redis=redis,
        license_id=license_id,
        actor_id=current_user.id,
        request=body,
    )
