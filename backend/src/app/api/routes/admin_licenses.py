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

import html
from typing import Optional

import structlog
from aiosmtplib import SMTP
from email.message import EmailMessage
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


async def _send_license_delivery_email(
    to_email: str,
    raw_key: str,
    tier_label: str,
    max_devices: int,
    expired_at: Optional[str],
) -> None:
    """Send a license delivery email with the raw key to the customer."""
    from app.core.config import get_settings as core_get_settings

    settings = core_get_settings()
    if not settings.smtp_user or not settings.smtp_password.get_secret_value():
        log.warning("smtp_not_configured_skipping_license_email", to=to_email)
        return

    safe_key = html.escape(raw_key)
    safe_tier = html.escape(tier_label)
    expiry_display = expired_at or "No expiry set"
    safe_expiry = html.escape(expiry_display)
    app_url = settings.app_url.rstrip("/")

    text_body = (
        f"Forma — Your License Key\n"
        f"========================\n\n"
        f"Your license has been issued. Here are your details:\n\n"
        f"  Tier: {tier_label}\n"
        f"  Devices: {max_devices}\n"
        f"  Expires: {expiry_display}\n\n"
        f"License key:\n"
        f"{raw_key}\n\n"
        f"To activate your license:\n"
        f"  1. Go to {app_url}/activate\n"
        f"  2. Enter your license key\n\n"
        f"— The Forma team\n"
    )

    html_body = f"""
    <html>
      <body style="margin:0;padding:0;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,'Helvetica Neue',Arial,sans-serif;color:#18181b;background-color:#f4f4f5;">
        <table width="100%" cellpadding="0" cellspacing="0" style="background-color:#f4f4f5;padding:40px 16px;">
          <tr>
            <td align="center">
              <table width="560" cellpadding="0" cellspacing="0" style="background-color:#ffffff;border-radius:12px;overflow:hidden;box-shadow:0 1px 3px rgba(0,0,0,0.08);">
                <!-- Header -->
                <tr>
                  <td style="background-color:#1a1a2e;padding:32px 40px;text-align:center;">
                    <p style="margin:0;font-size:11px;letter-spacing:3px;color:#818cf8;text-transform:uppercase;font-weight:700;">Forma</p>
                    <h1 style="margin:12px 0 0;font-size:24px;font-weight:700;color:#ffffff;letter-spacing:-0.5px;">Your license is ready</h1>
                  </td>
                </tr>
                <!-- Body -->
                <tr>
                  <td style="padding:40px;">
                    <!-- Plan badge -->
                    <div style="display:inline-block;background-color:#eef2ff;border:1px solid #c7d2fe;border-radius:9999px;padding:6px 16px;margin-bottom:24px;">
                      <span style="font-size:14px;font-weight:700;color:#4338ca;">{safe_tier} plan</span>
                    </div>

                    <p style="margin:0 0 28px;font-size:16px;line-height:1.6;color:#3f3f46;">
                      Your Forma license has been issued. Save the license key below — it will only be shown once.
                    </p>

                    <!-- License details -->
                    <table cellpadding="0" cellspacing="0" width="100%" style="margin-bottom:24px;">
                      <tr>
                        <td style="padding:12px 16px;background-color:#fafafa;border-radius:8px;border:1px solid #f4f4f5;">
                          <p style="margin:0;font-size:12px;color:#71717a;font-weight:600;text-transform:uppercase;letter-spacing:0.5px;">License key</p>
                          <p style="margin:8px 0 0;font-size:15px;font-family:monospace;color:#18181b;word-break:break-all;letter-spacing:1px;">{safe_key}</p>
                        </td>
                      </tr>
                    </table>

                    <!-- Meta info -->
                    <table cellpadding="0" cellspacing="0" width="100%" style="margin-bottom:28px;">
                      <tr>
                        <td style="padding:10px 0;border-bottom:1px solid #f4f4f5;">
                          <span style="font-size:14px;color:#71717a;">Tier</span>
                          <span style="font-size:14px;color:#18181b;float:right;font-weight:600;">{safe_tier}</span>
                        </td>
                      </tr>
                      <tr>
                        <td style="padding:10px 0;border-bottom:1px solid #f4f4f5;">
                          <span style="font-size:14px;color:#71717a;">Max devices</span>
                          <span style="font-size:14px;color:#18181b;float:right;font-weight:600;">{max_devices}</span>
                        </td>
                      </tr>
                      <tr>
                        <td style="padding:10px 0;">
                          <span style="font-size:14px;color:#71717a;">Expires</span>
                          <span style="font-size:14px;color:#18181b;float:right;font-weight:600;">{safe_expiry}</span>
                        </td>
                      </tr>
                    </table>

                    <!-- CTA -->
                    <table cellpadding="0" cellspacing="0" style="margin:0 auto 16px;">
                      <tr>
                        <td style="background-color:#6366f1;border-radius:8px;text-align:center;">
                          <a href="{app_url}/activate" style="display:inline-block;padding:14px 32px;font-size:15px;font-weight:600;color:#ffffff;text-decoration:none;letter-spacing:-0.2px;">Activate your license</a>
                        </td>
                      </tr>
                    </table>
                    <p style="margin:0;font-size:14px;color:#71717a;text-align:center;">
                      Paste your license key on the activation page to get started.
                    </p>
                  </td>
                </tr>
                <!-- Footer -->
                <tr>
                  <td style="background-color:#fafafa;padding:24px 40px;border-top:1px solid #f4f4f5;">
                    <p style="margin:0;font-size:12px;color:#a1a1aa;text-align:center;">
                      — The Forma team
                    </p>
                  </td>
                </tr>
              </table>
            </td>
          </tr>
        </table>
      </body>
    </html>
    """.strip()

    msg = EmailMessage()
    msg["From"] = settings.smtp_from
    msg["To"] = to_email
    msg["Subject"] = f"Forma — your {tier_label} license key is ready"
    msg.set_content(text_body)
    msg.add_alternative(html_body, subtype="html")

    try:
        smtp = SMTP(
            hostname=settings.smtp_host,
            port=settings.smtp_port,
            start_tls=settings.smtp_tls,
        )
        await smtp.connect()
        await smtp.login(settings.smtp_user, settings.smtp_password.get_secret_value())
        await smtp.send_message(msg)
        await smtp.quit()
        log.info("license_delivery_email_sent", to=to_email, tier=tier_label)
    except Exception as exc:
        log.error(
            "license_delivery_email_failed",
            to=to_email,
            tier=tier_label,
            error=str(exc),
        )


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

    result = await license_service.create_license(
        session=session,
        request=internal_req,
        actor_id=current_user.id,
        signing_secret=settings.license_signing_secret.get_secret_value(),
        idempotency_key=idempotency_key,
    )

    if body.send_email and result.raw_key is not None:
        tier_label = str(result.license.tier).title()
        max_dev = result.license.max_devices or 1
        expiry_iso = result.license.expired_at if result.license.expired_at else None
        await _send_license_delivery_email(
            to_email=customer_user.email,
            raw_key=result.raw_key,
            tier_label=tier_label,
            max_devices=max_dev,
            expired_at=expiry_iso,
        )

    return result


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
