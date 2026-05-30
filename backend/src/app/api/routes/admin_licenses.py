"""
Admin license management routes — TASK-2.1.

POST /admin/licenses  — create a new license (admin only, idempotent via header)
"""
from __future__ import annotations

import structlog
from fastapi import APIRouter, Depends, Header, status
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Optional

from app.api.deps import get_settings, get_current_active_user, require_admin
from app.db.models import User
from app.db.session import get_session
from app.schemas.license import CreateLicenseRequest, LicenseResponse
from app.services import license_service

log = structlog.get_logger()

router = APIRouter(prefix="/admin", tags=["admin-licenses"])


@router.post(
    "/licenses",
    response_model=LicenseResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new license (admin only)",
)
async def create_license(
    body: CreateLicenseRequest,
    idempotency_key: Optional[str] = Header(default=None, alias="Idempotency-Key"),
    current_user: User = Depends(require_admin),
    session: AsyncSession = Depends(get_session),
    settings=Depends(get_settings),
) -> LicenseResponse:
    """Create a new license.

    - Requires admin (is_superuser=True).
    - Idempotency-Key header: repeat POSTs with the same key return the
      existing license (201) without inserting a duplicate.
    - raw_key is returned exactly once in the 201 response; it is never
      persisted (only its SHA-256 hash is stored).
    """
    return await license_service.create_license(
        session=session,
        request=body,
        actor_id=current_user.id,
        signing_secret=settings.license_signing_secret.get_secret_value(),
        idempotency_key=idempotency_key,
    )
